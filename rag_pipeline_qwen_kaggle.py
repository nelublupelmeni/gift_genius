import math
import os
import re
import urllib.parse
from collections import Counter
from typing import List, Tuple

import pandas as pd
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

# =========================
# Конфиг
# =========================
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen3.5-4B")
DATA_PATH = os.getenv(
    "DATA_PATH",
    "/kaggle/input/datasets/ursofiia/gift-genius-dataset/gifts_dataset_ru_plus (1).csv",
)
FINAL_TOP_K = int(os.getenv("FINAL_TOP_K", "15"))
ENABLE_THINKING = os.getenv("ENABLE_THINKING", "false").lower() == "true"
LLM_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

GEN_CONFIG = {
    "temperature": float(os.getenv("GEN_TEMPERATURE", "0.7")),
    "top_p": float(os.getenv("GEN_TOP_P", "0.8")),
    "top_k": int(os.getenv("GEN_TOP_K", "20")),
    "repetition_penalty": float(os.getenv("GEN_REPETITION_PENALTY", "1.05")),
}

print("=" * 60)
print("🎁 GiftGenius | Kaggle backend without external LLM API")
print("=" * 60)
print(f"LLM model: {MODEL_NAME}")
print(f"LLM device: {LLM_DEVICE}")
print(f"Thinking mode: {ENABLE_THINKING}")
print("Retrieval: pure-python BM25 (no sentence-transformers / no scipy)")
print("=" * 60)


def normalize_product_name(name: str) -> str:
    name = re.sub(r"[‑–—]", "-", name)
    name = re.sub(r"\s+", " ", name).strip()
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


# =========================
# Data + retrieval
# =========================
print("\n📊 Загрузка датасета...")
if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(f"DATA_PATH не найден: {DATA_PATH}")

df = pd.read_csv(DATA_PATH).fillna("")
print(f"✅ Подарков в базе: {len(df)}")

df["_doc"] = df.astype(str).agg(" | ".join, axis=1).str.strip()
corpus = df["_doc"].tolist()


def tokenize(text: str) -> List[str]:
    text = str(text).lower().replace("ё", "е")
    return re.findall(r"[a-zа-я0-9]+", text)


print("\n🔍 Построение BM25 индекса...")
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
IDF = {}
for tok, dfreq in doc_freq.items():
    IDF[tok] = math.log(1 + (N - dfreq + 0.5) / (dfreq + 0.5))

K1 = 1.5
B = 0.75
print(f"✅ BM25 готов | docs={N} | avgdl={avgdl:.1f}")


_OCCASION_HINTS = {
    "день рождения": ["день", "рождения", "др", "юбилей"],
    "новый год": ["новый", "год", "новогодний"],
    "свадьба": ["свадьба", "молодожены"],
    "8 марта": ["8", "марта"],
    "23 февраля": ["23", "февраля"],
}


def bm25_score(query_tokens: List[str], doc_idx: int) -> float:
    tf = doc_term_freqs[doc_idx]
    dl = doc_lens[doc_idx]
    score = 0.0
    for tok in query_tokens:
        freq = tf.get(tok, 0)
        if freq == 0:
            continue
        idf = IDF.get(tok, 0.0)
        denom = freq + K1 * (1 - B + B * dl / max(avgdl, 1e-9))
        score += idf * (freq * (K1 + 1)) / max(denom, 1e-9)
    return score



def retrieve_for_query(query_text: str, top_k: int = FINAL_TOP_K) -> List[int]:
    query_tokens = tokenize(query_text)
    if not query_tokens:
        return list(range(min(top_k, len(df))))

    scores = []
    raw_query = query_text.lower().replace("ё", "е")
    for i, doc_text in enumerate(corpus):
        score = bm25_score(query_tokens, i)

        # Лёгкие бусты для точных фраз и названий категорий.
        doc_lower = str(doc_text).lower().replace("ё", "е")
        for tok in set(query_tokens):
            if tok in doc_lower:
                score += 0.12
        if raw_query in doc_lower:
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


# =========================
# Parsing user request
# =========================
def extract_budget(query: str) -> str | None:
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



def detect_occasion(query: str) -> str | None:
    q = query.lower()
    for kw, label in OCCASION_MAP.items():
        if kw in q:
            return label
    return None


_RECIPIENT_HINTS = [
    "маме", "папе", "другу", "подруге", "коллеге", "брату", "сестре",
    "мужу", "жене", "дедушке", "бабушке", "ребёнку", "ребенку", "девушке", "парню",
]



def is_query_too_vague(query: str) -> bool:
    words = query.lower().split()
    has_who = any(h in words for h in _RECIPIENT_HINTS)
    return len(words) < 4 and not has_who


# =========================
# LLM loading (4-bit Qwen on one T4)
# =========================
print("\n🤖 Загрузка Qwen3.5-4B в 4-bit...")
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
print("✅ Qwen загружен")



def _apply_chat_template(messages: list[dict]) -> str:
    try:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=ENABLE_THINKING,
        )
    except TypeError:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )


@torch.inference_mode()
def call_local_llm(
    system_prompt: str,
    user_prompt: str,
    max_new_tokens: int = 512,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
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

    new_tokens = generated_ids[:, inputs["input_ids"].shape[1] :]
    text = tokenizer.batch_decode(
        new_tokens,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0].strip()

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text


# =========================
# Prompts
# =========================
PERSONA_SYSTEM = """Ты — психолог и gift-strategist.
Составь краткий, но полезный портрет получателя подарка.

Нужно описать:
1. возраст/роль/тип получателя, если можно понять из запроса;
2. образ жизни и интересы;
3. что может его порадовать;
4. какие ограничения есть в выборе подарка.

Пиши по-русски, 4-6 предложений, без воды."""



def persona_prompt(query: str, occasion: str | None = None, budget: str | None = None) -> str:
    ctx = ""
    if occasion:
        ctx += f"Повод: {occasion}\n"
    if budget:
        ctx += f"Бюджет: {budget}\n"
    return f'Запрос: "{query}"\n{ctx}\nСделай содержательный портрет человека для подбора подарка.'


ANTI_SYSTEM = """Ты — аналитик по подбору подарков.
На основе портрета выдели категории подарков, которые лучше НЕ дарить.

Верни 3-5 коротких пунктов на русском языке.
Каждый пункт — отдельной строкой и начинается с дефиса."""



def anti_prompt(query: str, persona: str) -> str:
    return f"""ПОРТРЕТ:
{persona}

ИСХОДНЫЙ ЗАПРОС:
{query}

Выдели 3-5 нежелательных категорий подарков."""


CREATIVE_SYSTEM = """Ты — сильный эксперт по подбору подарков.
Сгенерируй 5 качественных идей подарков по-русски.

Обязательные правила:
- идеи должны быть реалистичными и доступными для покупки;
- нельзя предлагать банальности вроде носков, кружек и случайных сувениров;
- названия должны быть конкретными и понятными для поиска на маркетплейсах;
- учитывай характер, интересы, повод и бюджет, если они известны;
- не повторяй одну и ту же категорию подарка разными словами.

Для каждой идеи строго используй формат:
ПОДАРОК: ...
ПОЧЕМУ: ...
МОМЕНТ: ...
ЧЕМ НЕ БАНАЛЬНО: ...
"""



def creative_prompt(
    query: str,
    persona: str,
    anti_list: List[str],
    products: List[str],
    budget: str | None = None,
    occasion: str | None = None,
) -> str:
    products_list = "\n".join([f"- {p}" for p in products[:10]])
    anti_list_text = "\n".join([f"- {item.lstrip('- ').strip()}" for item in anti_list[:5]])

    ctx = ""
    if occasion:
        ctx += f"Повод: {occasion}\n"
    if budget:
        ctx += f"Бюджет: {budget}\n"

    return f"""ПОРТРЕТ ПОЛУЧАТЕЛЯ:
{persona}

НЕЖЕЛАТЕЛЬНЫЕ ПОДАРКИ:
{anti_list_text}

{ctx}РЕФЕРЕНСЫ ИЗ БАЗЫ ТОВАРОВ (не копируй их дословно, используй как ориентир категорий):
{products_list}

ЗАДАЧА:
Придумай 5 разных персонализированных идей подарков для этого запроса: {query}

Начинай сразу с первой идеи и соблюдай формат без дополнительных вступлений."""


# =========================
# Parsing output
# =========================
def parse_ideas(creative_response: str) -> List[str]:
    ideas = []
    current_idea = []

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

    return ideas[:5]



def extract_idea_title(idea_text: str) -> str:
    for line in idea_text.split("\n"):
        if line.startswith("ПОДАРОК:"):
            return line.replace("ПОДАРОК:", "").strip().strip("*")
    return ""


# =========================
# Main pipeline
# =========================
def gift_agent(query: str, verbose: bool = True):
    if verbose:
        print(f"\n🔍 Обработка запроса: {query}")

    budget = extract_budget(query)
    occasion = detect_occasion(query)

    if is_query_too_vague(query):
        return {
            "status": "needs_clarification",
            "questions": "Уточните, пожалуйста, кому подарок, возраст/роль человека и его интересы.",
        }

    if verbose:
        print("[1/4] Поиск релевантных товаров в базе...")
    idx = retrieve_for_query(query)
    products, _ = get_products_context(idx)

    if verbose:
        print(f"   Найдено референсов: {len(products)}")
        print("[2/4] Создание портрета...")
    persona = call_local_llm(
        PERSONA_SYSTEM,
        persona_prompt(query, occasion, budget),
        max_new_tokens=220,
    )
    if not persona:
        persona = "Получатель любит персональные и осмысленные подарки, подобранные под интересы и образ жизни."

    if verbose:
        print("[3/4] Выделение анти-предпочтений...")
    anti_response = call_local_llm(
        ANTI_SYSTEM,
        anti_prompt(query, persona),
        max_new_tokens=180,
    )
    anti_list = [line.strip() for line in anti_response.split("\n") if line.strip()]
    if not anti_list:
        anti_list = ["- Банальные сувениры", "- Слишком обезличенные подарки"]

    if verbose:
        print("[4/4] Генерация идей подарков...")
    creative_response = call_local_llm(
        CREATIVE_SYSTEM,
        creative_prompt(query, persona, anti_list, products, budget, occasion),
        max_new_tokens=700,
    )

    ideas = parse_ideas(creative_response)
    if not ideas:
        ideas = [
            f"ПОДАРОК: {p}\nПОЧЕМУ: Подходит по интересам и контексту запроса.\nМОМЕНТ: Такой подарок будет уместен и полезен в повседневной жизни.\nЧЕМ НЕ БАНАЛЬНО: Он связан с реальными увлечениями человека, а не выбран случайно."
            for p in products[:5]
        ]

    if verbose:
        print(f"✅ Сгенерировано идей: {len(ideas)}")

    return {
        "status": "success",
        "ideas": ideas,
        "budget": budget,
        "occasion": occasion,
        "persona": persona,
        "anti_list": anti_list,
        "references": products[:10],
    }



def generate_gifts(description: str) -> List[str]:
    try:
        result = gift_agent(description, verbose=False)
        if result["status"] == "needs_clarification":
            return [f"Уточните: {result['questions']}"]
        return result.get("ideas", ["Идеи не найдены"])
    except Exception as e:
        print(f"❌ Ошибка generate_gifts: {e}")
        return [f"Ошибка: {e}"]


print("\n✅ Backend готов: BM25 retrieval на CPU, Qwen 4-bit на GPU")
