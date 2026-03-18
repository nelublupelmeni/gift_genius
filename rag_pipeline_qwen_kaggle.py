import math
import os
import re
import urllib.parse
from collections import Counter
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict

import pandas as pd
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

try:
    from langgraph.constants import END, START
    from langgraph.graph import StateGraph
    LANGGRAPH_AVAILABLE = True
except Exception:
    LANGGRAPH_AVAILABLE = False
    START = "__start__"
    END = "__end__"


# ============================================================
# Config
# ============================================================
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-3B-Instruct")
DATA_PATH = os.getenv(
    "DATA_PATH",
    "/kaggle/input/datasets/ursofiia/gift-genius-dataset/gifts_dataset_ru_plus (1).csv",
)
FINAL_TOP_K = int(os.getenv("FINAL_TOP_K", "20"))
IDEAS_TO_GENERATE = int(os.getenv("IDEAS_TO_GENERATE", "10"))
MAX_GENERATION_RETRIES = int(os.getenv("MAX_GENERATION_RETRIES", "1"))
ENABLE_THINKING = os.getenv("ENABLE_THINKING", "false").lower() == "true"
LLM_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

GEN_CONFIG = {
    "temperature": float(os.getenv("GEN_TEMPERATURE", "0.55")),
    "top_p": float(os.getenv("GEN_TOP_P", "0.85")),
    "top_k": int(os.getenv("GEN_TOP_K", "40")),
    "repetition_penalty": float(os.getenv("GEN_REPETITION_PENALTY", "1.05")),
}


# ============================================================
# Helpers
# ============================================================
def normalize_text(text: str) -> str:
    text = str(text or "")
    text = text.replace("ё", "е")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_product_name(name: str) -> str:
    name = re.sub(r"[‑–—]", "-", normalize_text(name))
    return name


def create_market_links(product_name: str) -> dict:
    clean_name = normalize_product_name(product_name.split(",")[0].strip().strip('"'))
    encoded_wb = urllib.parse.quote(clean_name)
    encoded_ya = urllib.parse.quote(clean_name).replace("%20", "+")
    encoded_ozon = urllib.parse.quote(clean_name)
    return {
        "wildberries": f"https://www.wildberries.ru/catalog/0/search.aspx?search={encoded_wb}",
        "yamarket": f"https://market.yandex.ru/search?text={encoded_ya}",
        "ozon": f"https://www.ozon.ru/search/?text={encoded_ozon}",
    }


# ============================================================
# Dataset + BM25 retrieval
# ============================================================
if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(f"DATA_PATH не найден: {DATA_PATH}")

df = pd.read_csv(DATA_PATH).fillna("")
df["_doc"] = df.astype(str).agg(" | ".join, axis=1).str.strip()
corpus = df["_doc"].tolist()


def tokenize(text: str) -> List[str]:
    text = normalize_text(text).lower()
    return re.findall(r"[a-zа-я0-9]+", text)


corpus_tokens = [tokenize(doc) for doc in corpus]
doc_lens = [len(tokens) for tokens in corpus_tokens]
avgdl = sum(doc_lens) / max(len(doc_lens), 1)
doc_freq = Counter()
doc_term_freqs = []
for tokens in corpus_tokens:
    tf = Counter(tokens)
    doc_term_freqs.append(tf)
    for tok in tf.keys():
        doc_freq[tok] += 1

N = len(corpus_tokens)
IDF = {tok: math.log(1 + (N - dfreq + 0.5) / (dfreq + 0.5)) for tok, dfreq in doc_freq.items()}
K1 = 1.5
B = 0.75


def bm25_score(query_tokens: List[str], doc_idx: int) -> float:
    tf = doc_term_freqs[doc_idx]
    dl = doc_lens[doc_idx]
    score = 0.0
    for tok in query_tokens:
        freq = tf.get(tok, 0)
        if not freq:
            continue
        idf = IDF.get(tok, 0.0)
        denom = freq + K1 * (1 - B + B * dl / max(avgdl, 1e-9))
        score += idf * (freq * (K1 + 1)) / max(denom, 1e-9)
    return score


def retrieve_for_query(query_text: str, top_k: int = FINAL_TOP_K) -> List[int]:
    query_tokens = tokenize(query_text)
    if not query_tokens:
        return list(range(min(top_k, len(df))))

    raw_query = normalize_text(query_text).lower()
    scores = []
    for i, doc_text in enumerate(corpus):
        score = bm25_score(query_tokens, i)
        doc_lower = normalize_text(doc_text).lower()
        for tok in set(query_tokens):
            if tok in doc_lower:
                score += 0.12
        if raw_query and raw_query in doc_lower:
            score += 1.0
        scores.append((score, i))

    scores.sort(key=lambda x: x[0], reverse=True)
    return [i for _, i in scores[: max(top_k * 2, 20)]]


def get_products_context(idx_list: List[int], top_k: int = FINAL_TOP_K) -> Tuple[List[str], pd.DataFrame]:
    context_df = df.iloc[idx_list[:top_k]].copy()
    products = []
    for _, row in context_df.iterrows():
        name = str(row.iloc[0]).split(",")[0].strip().strip('"')
        products.append(name)
    return products, context_df


# ============================================================
# Query parsing
# ============================================================
OCCASION_MAP = {
    "день рождения": "День рождения",
    "новый год": "Новый год",
    "свадьба": "Свадьба",
    "8 марта": "8 марта",
    "23 февраля": "23 февраля",
    "юбилей": "Юбилей",
    "годовщина": "Годовщина",
    "рождение ребенка": "Рождение ребенка",
}

RECIPIENT_HINTS = [
    "маме", "папе", "другу", "подруге", "коллеге", "брату", "сестре", "мужу", "жене",
    "дедушке", "бабушке", "ребенку", "ребёнку", "девушке", "парню", "сыну", "дочери",
]

INTEREST_HINTS = [
    "кофе", "йога", "спорт", "рыбалка", "музыка", "гитара", "книги", "чтение", "гейминг",
    "программирование", "дача", "путешествия", "готовить", "фото", "рисование", "вино",
    "веганство", "механические клавиатуры", "настолки",
]


def extract_budget(query: str) -> Optional[str]:
    patterns = [
        r"(?:до|не более|максимум)\s+(\d[\d\s]*)\s*(?:руб|р\b|₽|тыс|k|к)",
        r"(\d[\d\s]*)\s*(?:–|-)\s*(\d[\d\s]*)\s*(?:руб|р\b|₽)",
        r"бюджет[: ]+(\d[\d\s]*)\s*(?:руб|р\b|₽|тыс|k|к)?",
    ]
    for p in patterns:
        m = re.search(p, query, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return None


def detect_occasion(query: str) -> Optional[str]:
    q = normalize_text(query).lower()
    for kw, label in OCCASION_MAP.items():
        if kw in q:
            return label
    return None


def extract_recipient(query: str) -> Optional[str]:
    q = normalize_text(query).lower()
    for hint in RECIPIENT_HINTS:
        if hint in q:
            return hint
    return None


def extract_interests(query: str) -> List[str]:
    q = normalize_text(query).lower()
    found = [hint for hint in INTEREST_HINTS if hint in q]
    return found[:5]


def is_query_too_vague(query: str) -> bool:
    words = tokenize(query)
    has_recipient = any(h in normalize_text(query).lower() for h in RECIPIENT_HINTS)
    has_interest = any(i in normalize_text(query).lower() for i in INTEREST_HINTS)
    return len(words) < 4 or (not has_recipient and not has_interest and len(words) < 7)


# ============================================================
# LLM
# ============================================================
quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.float16,
)

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    quantization_config=quant_config,
    device_map="auto",
    torch_dtype=torch.float16,
    trust_remote_code=True,
    low_cpu_mem_usage=True,
)
model.eval()


def _apply_chat_template(messages: list[dict]) -> str:
    try:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=ENABLE_THINKING,
        )
    except TypeError:
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


@torch.inference_mode()
def call_local_llm(
    system_prompt: str,
    user_prompt: str,
    max_new_tokens: int = 512,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
) -> str:
    temperature = GEN_CONFIG["temperature"] if temperature is None else temperature
    top_p = GEN_CONFIG["top_p"] if top_p is None else top_p
    top_k = GEN_CONFIG["top_k"] if top_k is None else top_k

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    prompt = _apply_chat_template(messages)
    inputs = tokenizer(prompt, return_tensors="pt")
    target_device = "cuda:0" if torch.cuda.is_available() else "cpu"
    inputs = {k: v.to(target_device) for k, v in inputs.items()}

    generated_ids = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=temperature > 0,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        repetition_penalty=GEN_CONFIG["repetition_penalty"],
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
        use_cache=True,
    )

    new_tokens = generated_ids[:, inputs["input_ids"].shape[1]:]
    text = tokenizer.batch_decode(new_tokens, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0].strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text


# ============================================================
# Prompts
# ============================================================
PROCESS_SYSTEM = """Ты — агент нормализации gift-запросов.
Сделай запрос более структурированным, но ничего не выдумывай.
Выведи строго в формате:
Кому: ...
Возраст/роль: ...
Повод: ...
Бюджет: ...
Интересы: ...
Ограничения: ...
Короткий запрос: ...
"""

VALIDATE_QUERY_SYSTEM = """Ты — валидатор gift-запроса.
Проверь, хватает ли данных для старта подбора подарков.
Ответь строго в JSON-подобном виде без пояснений:
valid: yes/no
reason: ...
need: ...
"""

PERSONA_SYSTEM = """Ты — психолог и gift-strategist.
Составь краткий, но полезный портрет получателя подарка.
Нужно описать:
1. возраст/роль/тип получателя, если можно понять из запроса;
2. образ жизни и интересы;
3. что может его порадовать;
4. какие ограничения есть в выборе подарка.
Пиши по-русски, 4-6 предложений, без воды.
"""

ANTI_SYSTEM = """Ты — аналитик по подбору подарков.
На основе портрета выдели категории подарков, которые лучше НЕ дарить.
Верни 3-5 коротких пунктов на русском языке.
Каждый пункт — отдельной строкой и начинается с дефиса.
"""

CREATIVE_SYSTEM = f"""Ты — сильный эксперт по подбору подарков.
Сгенерируй {IDEAS_TO_GENERATE} качественных идей подарков по-русски.

Правила:
- идеи должны быть реалистичными и доступными для покупки;
- нельзя предлагать банальности вроде носков, кружек и случайных сувениров;
- названия должны быть конкретными и понятными для поиска на маркетплейсах;
- учитывай характер, интересы, повод и бюджет, если они известны;
- не повторяй одну и ту же категорию подарка разными словами;
- выведи не меньше {IDEAS_TO_GENERATE} идей.

Для каждой идеи строго используй формат:
ПОДАРОК: ...
ПОЧЕМУ: ...
МОМЕНТ: ...
ЧЕМ НЕ БАНАЛЬНО: ...
"""

VALIDATE_GIFTS_SYSTEM = """Ты — строгий редактор gift-идей.
Проверь список идей по критериям:
- персонализация,
- небанальность,
- конкретность названия,
- разнообразие,
- пригодность для поиска на маркетплейсе.
Верни строго:
verdict: good/bad
issues:
- ...
- ...
"""


# ============================================================
# Parsing outputs
# ============================================================
def persona_prompt(query: str, occasion: Optional[str] = None, budget: Optional[str] = None) -> str:
    ctx = ""
    if occasion:
        ctx += f"Повод: {occasion}\n"
    if budget:
        ctx += f"Бюджет: {budget}\n"
    return f'Запрос: "{query}"\n{ctx}\nСделай содержательный портрет человека для подбора подарка.'


def anti_prompt(query: str, persona: str) -> str:
    return f"""ПОРТРЕТ:\n{persona}\n\nИСХОДНЫЙ ЗАПРОС:\n{query}\n\nВыдели 3-5 нежелательных категорий подарков."""


def creative_prompt(
    query: str,
    persona: str,
    anti_list: List[str],
    products: List[str],
    budget: Optional[str] = None,
    occasion: Optional[str] = None,
    validator_feedback: Optional[str] = None,
) -> str:
    products_list = "\n".join([f"- {p}" for p in products[:12]])
    anti_list_text = "\n".join([f"- {item.lstrip('- ').strip()}" for item in anti_list[:5]])
    ctx = ""
    if occasion:
        ctx += f"Повод: {occasion}\n"
    if budget:
        ctx += f"Бюджет: {budget}\n"
    if validator_feedback:
        ctx += f"Исправь ошибки прошлой генерации: {validator_feedback}\n"
    return f"""ПОРТРЕТ ПОЛУЧАТЕЛЯ:\n{persona}\n\nНЕЖЕЛАТЕЛЬНЫЕ ПОДАРКИ:\n{anti_list_text}\n\n{ctx}РЕФЕРЕНСЫ ИЗ БАЗЫ ТОВАРОВ (не копируй дословно, используй как ориентир категорий):\n{products_list}\n\nЗАДАЧА:\nПридумай {IDEAS_TO_GENERATE} разных персонализированных идей подарков для запроса: {query}\n\nНачинай сразу с первой идеи и соблюдай формат без вступлений."""


def validate_ideas_prompt(query: str, persona: str, ideas_text: str) -> str:
    return f"""ИСХОДНЫЙ ЗАПРОС:\n{query}\n\nПОРТРЕТ:\n{persona}\n\nИДЕИ:\n{ideas_text}\n\nОцени качество списка."""


def parse_validation_output(text: str) -> Dict[str, str]:
    valid = "no"
    reason = ""
    need = ""
    for line in text.splitlines():
        l = line.strip()
        if l.lower().startswith("valid:"):
            valid = l.split(":", 1)[1].strip().lower()
        elif l.lower().startswith("reason:"):
            reason = l.split(":", 1)[1].strip()
        elif l.lower().startswith("need:"):
            need = l.split(":", 1)[1].strip()
    return {"valid": valid, "reason": reason, "need": need}


def parse_gifts_validation(text: str) -> Dict[str, Any]:
    verdict = "bad"
    issues: List[str] = []
    for line in text.splitlines():
        l = line.strip()
        if l.lower().startswith("verdict:"):
            verdict = l.split(":", 1)[1].strip().lower()
        elif l.startswith("-"):
            issues.append(l)
    return {"verdict": verdict, "issues": issues}


def parse_ideas(creative_response: str) -> List[str]:
    ideas: List[str] = []
    current_idea: List[str] = []
    for raw_line in creative_response.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("ПОДАРОК:"):
            if current_idea:
                ideas.append("\n".join(current_idea))
                current_idea = []
            current_idea.append(line)
        elif line.startswith(("ПОЧЕМУ:", "МОМЕНТ:", "ЧЕМ НЕ БАНАЛЬНО:")):
            current_idea.append(line)
        elif current_idea:
            current_idea.append(line)
    if current_idea:
        ideas.append("\n".join(current_idea))
    return ideas


def extract_idea_title(idea_text: str) -> str:
    for line in idea_text.splitlines():
        if line.startswith("ПОДАРОК:"):
            return line.replace("ПОДАРОК:", "").strip().strip("*")
    return ""


def idea_quality_score(idea_text: str, query: str, persona: str) -> float:
    text = normalize_text(idea_text).lower()
    query_tokens = set(tokenize(query))
    persona_tokens = set(tokenize(persona))
    score = 0.0
    if "подарок:" in text:
        score += 1.0
    if "почему:" in text:
        score += 0.8
    if "момент:" in text:
        score += 0.6
    if "чем не банально:" in text:
        score += 1.0
    score += min(len(set(tokenize(text)) & query_tokens) * 0.15, 1.2)
    score += min(len(set(tokenize(text)) & persona_tokens) * 0.08, 0.8)
    title = extract_idea_title(idea_text)
    if len(title.split()) >= 2:
        score += 0.6
    if any(bad in text for bad in ["носки", "кружк", "сувенир"]):
        score -= 1.2
    return score


def dedupe_ideas(ideas: List[str]) -> List[str]:
    seen = set()
    result = []
    for idea in ideas:
        key = normalize_text(extract_idea_title(idea)).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(idea)
    return result


# ============================================================
# Graph state
# ============================================================
class GiftGraphState(TypedDict, total=False):
    raw_query: str
    normalized_query: str
    query_valid: bool
    clarification_question: str
    validation_reason: str
    budget: Optional[str]
    occasion: Optional[str]
    recipient: Optional[str]
    interests: List[str]
    persona: str
    anti_list: List[str]
    retrieved_products: List[str]
    references: List[str]
    generation_attempt: int
    generation_feedback: str
    draft_ideas: List[str]
    validated_ideas: List[str]
    validation_issues: List[str]
    search_links: Dict[str, Dict[str, str]]
    best_links: Dict[str, Dict[str, str]]
    final_ideas: List[str]
    feedback_report: str
    status: str
    debug_trace: List[str]


def add_trace(state: GiftGraphState, msg: str) -> GiftGraphState:
    trace = list(state.get("debug_trace", []))
    trace.append(msg)
    state["debug_trace"] = trace
    return state


# ============================================================
# Nodes
# ============================================================
def validate_input_node(state: GiftGraphState) -> GiftGraphState:
    query = normalize_text(state.get("raw_query", ""))
    state["raw_query"] = query
    if not query:
        state["query_valid"] = False
        state["status"] = "needs_clarification"
        state["clarification_question"] = "Опишите, кому нужен подарок, повод, бюджет и интересы человека."
        return add_trace(state, "validate_input: empty")
    if is_query_too_vague(query):
        state["query_valid"] = False
        state["status"] = "needs_clarification"
        state["clarification_question"] = "Уточните, пожалуйста, кому подарок, возраст/роль человека, его интересы и желаемый бюджет."
        return add_trace(state, "validate_input: vague")
    state["query_valid"] = True
    state["status"] = "ok"
    return add_trace(state, "validate_input: ok")


def process_query_node(state: GiftGraphState) -> GiftGraphState:
    query = state["raw_query"]
    state["budget"] = extract_budget(query)
    state["occasion"] = detect_occasion(query)
    state["recipient"] = extract_recipient(query)
    state["interests"] = extract_interests(query)
    structured = call_local_llm(PROCESS_SYSTEM, query, max_new_tokens=180, temperature=0.2)
    short_query = query
    m = re.search(r"Короткий запрос:\s*(.+)", structured)
    if m:
        short_query = m.group(1).strip()
    state["normalized_query"] = short_query
    return add_trace(state, "process_query: normalized")


def validate_processed_query_node(state: GiftGraphState) -> GiftGraphState:
    validation = call_local_llm(VALIDATE_QUERY_SYSTEM, state.get("normalized_query", state["raw_query"]), max_new_tokens=100, temperature=0.1)
    parsed = parse_validation_output(validation)
    state["validation_reason"] = parsed.get("reason", "")
    is_valid = parsed.get("valid", "no") == "yes"
    if not is_valid:
        state["query_valid"] = False
        state["status"] = "needs_clarification"
        need = parsed.get("need") or "Нужны получатель, интересы и бюджет."
        state["clarification_question"] = f"Уточните: {need}"
        return add_trace(state, "validate_processed_query: fail")
    state["query_valid"] = True
    return add_trace(state, "validate_processed_query: ok")


def persona_node(state: GiftGraphState) -> GiftGraphState:
    persona = call_local_llm(
        PERSONA_SYSTEM,
        persona_prompt(state["normalized_query"], state.get("occasion"), state.get("budget")),
        max_new_tokens=220,
        temperature=0.35,
    )
    if not persona:
        persona = "Получатель любит персональные и продуманные подарки, связанные с его образом жизни и интересами."
    state["persona"] = persona
    return add_trace(state, "persona: created")


def retrieve_node(state: GiftGraphState) -> GiftGraphState:
    query = " ".join([
        state.get("normalized_query", state["raw_query"]),
        state.get("occasion") or "",
        " ".join(state.get("interests", [])),
    ]).strip()
    idx = retrieve_for_query(query)
    products, _ = get_products_context(idx)
    state["retrieved_products"] = products[:FINAL_TOP_K]
    state["references"] = products[:10]
    return add_trace(state, f"retrieve: {len(products[:FINAL_TOP_K])} refs")


def anti_node(state: GiftGraphState) -> GiftGraphState:
    anti_response = call_local_llm(
        ANTI_SYSTEM,
        anti_prompt(state["normalized_query"], state["persona"]),
        max_new_tokens=180,
        temperature=0.25,
    )
    anti_list = [line.strip() for line in anti_response.splitlines() if line.strip().startswith("-")]
    if not anti_list:
        anti_list = ["- Банальные сувениры", "- Слишком обезличенные подарки"]
    state["anti_list"] = anti_list
    return add_trace(state, "anti: created")


def generate_gifts_node(state: GiftGraphState) -> GiftGraphState:
    creative_response = call_local_llm(
        CREATIVE_SYSTEM,
        creative_prompt(
            state["normalized_query"],
            state["persona"],
            state.get("anti_list", []),
            state.get("retrieved_products", []),
            state.get("budget"),
            state.get("occasion"),
            state.get("generation_feedback"),
        ),
        max_new_tokens=1200,
        temperature=0.6,
    )
    ideas = parse_ideas(creative_response)
    if not ideas:
        ideas = [
            f"ПОДАРОК: {p}\nПОЧЕМУ: Подходит по интересам и контексту запроса.\nМОМЕНТ: Такой подарок будет полезен и уместен.\nЧЕМ НЕ БАНАЛЬНО: Он связан с реальными увлечениями человека, а не выбран случайно."
            for p in state.get("retrieved_products", [])[:IDEAS_TO_GENERATE]
        ]
    state["draft_ideas"] = ideas[: max(IDEAS_TO_GENERATE, 5)]
    state["generation_attempt"] = int(state.get("generation_attempt", 0)) + 1
    return add_trace(state, f"generate_gifts: {len(state['draft_ideas'])} ideas")


def validate_gifts_node(state: GiftGraphState) -> GiftGraphState:
    ideas_text = "\n\n".join(state.get("draft_ideas", []))
    llm_check = call_local_llm(
        VALIDATE_GIFTS_SYSTEM,
        validate_ideas_prompt(state["normalized_query"], state["persona"], ideas_text),
        max_new_tokens=180,
        temperature=0.1,
    )
    parsed = parse_gifts_validation(llm_check)
    deduped = dedupe_ideas(state.get("draft_ideas", []))
    rescored = sorted(deduped, key=lambda x: idea_quality_score(x, state["normalized_query"], state["persona"]), reverse=True)

    enough_ideas = len(rescored) >= min(IDEAS_TO_GENERATE, 8)
    good_verdict = parsed["verdict"] == "good"
    structure_ok = sum(1 for i in rescored if "ЧЕМ НЕ БАНАЛЬНО:" in i and "ПОЧЕМУ:" in i) >= min(5, len(rescored))

    state["validated_ideas"] = rescored
    state["validation_issues"] = parsed.get("issues", [])
    if good_verdict and enough_ideas and structure_ok:
        state["status"] = "success"
        return add_trace(state, "validate_gifts: ok")

    if int(state.get("generation_attempt", 0)) <= MAX_GENERATION_RETRIES:
        issues = "; ".join(parsed.get("issues", [])) or "Сделай идеи разнообразнее и конкретнее."
        state["generation_feedback"] = issues
        state["status"] = "retry_generation"
        return add_trace(state, "validate_gifts: retry")

    state["status"] = "success"
    return add_trace(state, "validate_gifts: accept_after_retry")


def generate_links_node(state: GiftGraphState) -> GiftGraphState:
    links: Dict[str, Dict[str, str]] = {}
    for idea in state.get("validated_ideas", [])[:IDEAS_TO_GENERATE]:
        title = extract_idea_title(idea)
        if title:
            links[title] = create_market_links(title)
    state["search_links"] = links
    state["best_links"] = links
    return add_trace(state, f"generate_links: {len(links)}")


def rank_and_finalize_node(state: GiftGraphState) -> GiftGraphState:
    scored = sorted(
        state.get("validated_ideas", []),
        key=lambda x: idea_quality_score(x, state["normalized_query"], state["persona"]),
        reverse=True,
    )
    state["final_ideas"] = scored[:IDEAS_TO_GENERATE]
    return add_trace(state, f"finalize: {len(state['final_ideas'])}")


def feedback_node(state: GiftGraphState) -> GiftGraphState:
    remove = []
    add = []
    for issue in state.get("validation_issues", []):
        issue_norm = issue.lower()
        if "банал" in issue_norm or "повтор" in issue_norm:
            remove.append(issue)
        else:
            add.append(issue)
    state["feedback_report"] = (
        "Что убрать: " + ("; ".join(remove) if remove else "критичных повторов нет") + "\n"
        "Что добавить: " + ("; ".join(add) if add else "список уже достаточно сбалансирован")
    )
    return add_trace(state, "feedback: built")


# ============================================================
# Routing
# ============================================================
def route_after_input(state: GiftGraphState) -> Literal["process_query", END]:
    return "process_query" if state.get("query_valid") else END


def route_after_query_validation(state: GiftGraphState) -> Literal["persona", END]:
    return "persona" if state.get("query_valid") else END


def route_after_gift_validation(state: GiftGraphState) -> Literal["generate_gifts", "generate_links"]:
    return "generate_gifts" if state.get("status") == "retry_generation" else "generate_links"


# ============================================================
# Graph builder
# ============================================================
def build_gift_graph():
    if not LANGGRAPH_AVAILABLE:
        return None
    graph = StateGraph(GiftGraphState)
    graph.add_node("validate_input", validate_input_node)
    graph.add_node("process_query", process_query_node)
    graph.add_node("validate_processed_query", validate_processed_query_node)
    graph.add_node("persona", persona_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("anti", anti_node)
    graph.add_node("generate_gifts", generate_gifts_node)
    graph.add_node("validate_gifts", validate_gifts_node)
    graph.add_node("generate_links", generate_links_node)
    graph.add_node("finalize", rank_and_finalize_node)
    graph.add_node("feedback", feedback_node)

    graph.add_edge(START, "validate_input")
    graph.add_conditional_edges("validate_input", route_after_input)
    graph.add_edge("process_query", "validate_processed_query")
    graph.add_conditional_edges("validate_processed_query", route_after_query_validation)
    graph.add_edge("persona", "retrieve")
    graph.add_edge("retrieve", "anti")
    graph.add_edge("anti", "generate_gifts")
    graph.add_edge("generate_gifts", "validate_gifts")
    graph.add_conditional_edges("validate_gifts", route_after_gift_validation)
    graph.add_edge("generate_links", "finalize")
    graph.add_edge("finalize", "feedback")
    graph.add_edge("feedback", END)
    return graph.compile()


gift_graph = build_gift_graph()


# ============================================================
# Sequential fallback
# ============================================================
def run_sequential(state: GiftGraphState) -> GiftGraphState:
    state = validate_input_node(state)
    if not state.get("query_valid"):
        return state
    state = process_query_node(state)
    state = validate_processed_query_node(state)
    if not state.get("query_valid"):
        return state
    state = persona_node(state)
    state = retrieve_node(state)
    state = anti_node(state)
    state = generate_gifts_node(state)
    state = validate_gifts_node(state)
    if state.get("status") == "retry_generation":
        state = generate_gifts_node(state)
        state = validate_gifts_node(state)
    state = generate_links_node(state)
    state = rank_and_finalize_node(state)
    state = feedback_node(state)
    return state


# ============================================================
# Public API
# ============================================================
def gift_agent(query: str, verbose: bool = False) -> Dict[str, Any]:
    initial_state: GiftGraphState = {
        "raw_query": query,
        "generation_attempt": 0,
        "generation_feedback": "",
        "debug_trace": [],
        "status": "started",
    }
    result = gift_graph.invoke(initial_state) if gift_graph is not None else run_sequential(initial_state)

    if result.get("status") == "needs_clarification":
        return {
            "status": "needs_clarification",
            "questions": result.get("clarification_question", "Уточните запрос."),
            "debug_trace": result.get("debug_trace", []),
        }

    payload = {
        "status": "success",
        "ideas": result.get("final_ideas", []),
        "budget": result.get("budget"),
        "occasion": result.get("occasion"),
        "recipient": result.get("recipient"),
        "interests": result.get("interests", []),
        "persona": result.get("persona", ""),
        "anti_list": result.get("anti_list", []),
        "references": result.get("references", []),
        "search_links": result.get("best_links", {}),
        "feedback_report": result.get("feedback_report", ""),
        "debug_trace": result.get("debug_trace", []),
        "graph_mode": "langgraph" if gift_graph is not None else "sequential_fallback",
    }
    if verbose:
        return payload
    payload.pop("debug_trace", None)
    return payload



def generate_gifts(description: str) -> List[str]:
    result = gift_agent(description, verbose=False)
    if result["status"] == "needs_clarification":
        return [f"Уточните: {result['questions']}"]
    return result.get("ideas", ["Идеи не найдены"])
