import os
import re
import urllib.parse
import json
from datetime import datetime

import requests
import streamlit as st

st.set_page_config(
    page_title="GiftGenius",
    page_icon="🎁",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Кастомный CSS
st.markdown("""
<style>
    /* Главный контейнер */
    .main > div {
        padding: 1rem 2rem;
    }
    
    /* Карточка подарка */
    .gift-card {
        background: linear-gradient(135deg, #fff 0%, #fef7e0 100%);
        padding: 1.5rem;
        border-radius: 20px;
        margin: 1rem 0;
        border: 1px solid rgba(255, 75, 75, 0.2);
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .gift-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
    }
    
    .gift-title {
        font-size: 1.4rem;
        font-weight: 700;
        color: #ff4b4b;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #ff4b4b;
        display: inline-block;
    }
    
    .gift-description {
        background: white;
        padding: 1rem;
        border-radius: 12px;
        margin: 1rem 0;
        line-height: 1.6;
        color: #2c3e50;
        font-size: 0.95rem;
    }
    
    .links {
        margin-top: 1rem;
        padding-top: 0.75rem;
        border-top: 1px solid #eee;
        display: flex;
        gap: 0.75rem;
        flex-wrap: wrap;
    }
    
    .market-link {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        border-radius: 25px;
        text-decoration: none;
        font-weight: 500;
        font-size: 0.85rem;
        transition: all 0.2s;
        color: white;
    }
    .market-link:hover {
        transform: scale(1.02);
        opacity: 0.9;
    }
    
    .chat-message {
        padding: 0.75rem 1rem;
        border-radius: 15px;
        margin: 0.5rem 0;
        max-width: 85%;
        animation: fadeIn 0.3s ease;
    }
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin-left: auto;
        border-bottom-right-radius: 5px;
    }
    .assistant-message {
        background: #f0f2f6;
        color: #1a1a2e;
        border-bottom-left-radius: 5px;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .stButton > button {
        border-radius: 25px;
        font-weight: 500;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    .feedback-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 1.5rem;
        border-radius: 20px;
        margin-top: 2rem;
        border: 1px solid #dee2e6;
    }
    
    .badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 500;
        margin-right: 0.5rem;
    }
    .badge-success {
        background: #d4edda;
        color: #155724;
    }
    .badge-info {
        background: #d1ecf1;
        color: #0c5460;
    }
    
    .hero {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(135deg, #ff4b4b 0%, #ff8c42 100%);
        border-radius: 30px;
        margin-bottom: 2rem;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Инициализация сессии
def init_session():
    defaults = {
        "messages": [],
        "current_ideas": [],
        "iteration": 0,
        "query": "",
        "base_url": "",
        "dialog_active": False,
        "debug_info": []  # Добавляем для отладки
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session()

# ==================== УТИЛИТЫ ====================

def extract_gift_title(idea_text):
    """Извлекает название подарка"""
    match = re.search(r'ПОДАРОК:\s*([^\n]+)', idea_text)
    if match:
        return re.sub(r'[*"`]', '', match.group(1)).strip()
    match = re.match(r'^\d+\.\s*(.+)$', idea_text)
    if match:
        return match.group(1).strip()
    return None

def extract_gift_description(idea_text):
    """Извлекает описание"""
    parts = []
    for section in ['ПОЧЕМУ:', 'МОМЕНТ:', 'ЧЕМ НЕ БАНАЛЬНО:']:
        match = re.search(rf'{section}\s*([^\n]+)', idea_text)
        if match:
            parts.append(f"✨ {match.group(1).strip()}")
    return "\n\n".join(parts) if parts else None

def create_market_links(product_name):
    """Создает ссылки"""
    if not product_name:
        return []
    encoded = urllib.parse.quote(product_name.strip())
    return [
        ("🛍️ Wildberries", f"https://www.wildberries.ru/catalog/0/search.aspx?search={encoded}", "#9b59b6"),
        ("🎯 Яндекс Маркет", f"https://market.yandex.ru/search?text={encoded.replace('%20', '+')}", "#f1c40f"),
        ("📦 Ozon", f"https://www.ozon.ru/search/?text={encoded}", "#3498db"),
    ]

def display_gift_card(idea, index):
    """Отображает карточку подарка"""
    title = extract_gift_title(idea) or f"Идея #{index}"
    description = extract_gift_description(idea)
    
    with st.container():
        st.markdown(f"""
        <div class="gift-card">
            <div class="gift-title">🎁 {index}. {title}</div>
        """, unsafe_allow_html=True)
        
        if description:
            st.markdown(f'<div class="gift-description">{description}</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="links">', unsafe_allow_html=True)
        for name, url, color in create_market_links(title):
            st.markdown(f'<a href="{url}" target="_blank" class="market-link" style="background:{color};">{name}</a>', unsafe_allow_html=True)
        st.markdown('</div></div>', unsafe_allow_html=True)

def display_chat():
    """Отображает историю чата"""
    for msg in st.session_state.messages[-10:]:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-message user-message">💬 <b>Вы</b><br>{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-message assistant-message">🤖 <b>GiftGenius</b><br>{msg["content"]}</div>', unsafe_allow_html=True)

# ==================== API ВЫЗОВЫ (С ОТЛАДКОЙ) ====================

def call_api(description, feedback=None, iteration=0):
    """Вызов API с обработкой и отладкой"""
    base = st.session_state.base_url
    if not base:
        return None, "❌ Не указан URL API"
    
    url = f"{base}/generate_with_feedback"
    
    # Добавляем отладочную информацию
    debug_msg = f"📤 Отправка запроса: {url}\n📝 Описание: {description[:100]}..."
    st.session_state.debug_info.append(debug_msg)
    
    try:
        # Увеличиваем таймаут до 600 секунд (10 минут)
        response = requests.post(
            url,
            json={"description": description, "feedback": feedback, "iteration": iteration},
            timeout=600,
            headers={"Content-Type": "application/json"}
        )
        
        st.session_state.debug_info.append(f"📥 Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            st.session_state.debug_info.append(f"✅ Получено {len(result.get('ideas', []))} идей")
            return result, None
        else:
            error_text = f"❌ Ошибка {response.status_code}: {response.text[:200]}"
            st.session_state.debug_info.append(error_text)
            return None, error_text
            
    except requests.exceptions.ConnectionError as e:
        error = f"❌ Нет подключения к серверу: {e}"
        st.session_state.debug_info.append(error)
        return None, error
    except requests.exceptions.Timeout:
        error = "⏰ Таймаут. Сервер обрабатывает запрос слишком долго (>600 сек)"
        st.session_state.debug_info.append(error)
        return None, error
    except Exception as e:
        error = f"❌ Ошибка: {str(e)[:100]}"
        st.session_state.debug_info.append(error)
        return None, error

# ==================== ОСНОВНОЙ ИНТЕРФЕЙС ====================

# Хедер
st.markdown("""
<div class="hero">
    <h1>🎁 GiftGenius</h1>
    <p>ИИ-помощник для подбора идеальных подарков</p>
</div>
""", unsafe_allow_html=True)

# Настройка в сайдбаре
with st.sidebar:
    st.markdown("### ⚙️ Настройки")
    
    base_url = st.text_input(
        "🔗 URL Kaggle backend",
        value=st.session_state.base_url,
        placeholder="https://xxx.ngrok-free.dev",
        help="Вставьте URL из Kaggle ноутбука (например, https://walker-unerasable-will.ngrok-free.dev)"
    )
    st.session_state.base_url = base_url.strip().rstrip('/')
    
    if st.button("🔌 Проверить соединение", use_container_width=True):
        if st.session_state.base_url:
            with st.spinner("Проверка..."):
                try:
                    health_url = f"{st.session_state.base_url}/health"
                    r = requests.get(health_url, timeout=10)
                    if r.status_code == 200:
                        st.success(f"✅ Подключено! {r.json()}")
                    else:
                        st.error(f"❌ Ошибка {r.status_code}")
                except Exception as e:
                    st.error(f"❌ Не удалось подключиться: {e}")
        else:
            st.warning("Введите URL")
    
    st.divider()
    
    st.markdown("### 🎯 Быстрые примеры")
    examples = [
        "👩 Подруга, 30 лет, йога, любит читать",
        "👨 Папа, 55 лет, рыбалка, дача",
        "💻 Парень, 25 лет, программист, кофе и клавиатуры",
        "👩‍🍳 Мама, 50 лет, готовка, книги"
    ]
    
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}", use_container_width=True):
            st.session_state.query = ex
            st.session_state.messages = []
            st.session_state.current_ideas = []
            st.session_state.iteration = 0
            st.session_state.debug_info = []
            st.rerun()
    
    st.divider()
    
    if st.button("🔄 Сбросить диалог", use_container_width=True):
        st.session_state.messages = []
        st.session_state.current_ideas = []
        st.session_state.iteration = 0
        st.session_state.query = ""
        st.session_state.debug_info = []
        st.rerun()
    
    # Отладочная панель
    with st.expander("🐛 Отладка", expanded=False):
        if st.button("Очистить лог"):
            st.session_state.debug_info = []
        for msg in st.session_state.debug_info[-10:]:
            st.text(msg)

# Основной контент
col1, col2 = st.columns([3, 2])

with col1:
    st.markdown("### 📝 Кому нужен подарок?")
    
    query = st.text_area(
        "",
        value=st.session_state.query,
        placeholder="Опишите человека, интересы, повод...\n\nНапример: парень 25 лет, программист, любит кофе и механические клавиатуры",
        height=120,
        label_visibility="collapsed"
    )
    
    if query and query != st.session_state.query:
        st.session_state.query = query
        st.session_state.messages = []
        st.session_state.current_ideas = []
        st.session_state.iteration = 0
        st.session_state.debug_info = []

with col2:
    st.markdown("### ✨ Подсказки")
    st.info("💡 Чем подробнее описание, тем лучше подбор")
    st.caption("• Укажите возраст и пол")
    st.caption("• Перечислите интересы и хобби")
    st.caption("• Отметьте, что человек не любит")

# Кнопка генерации
if st.button("🎁 Найти подарки", type="primary", use_container_width=True):
    if not st.session_state.base_url:
        st.error("❌ Сначала укажите URL Kaggle backend в боковой панели")
    elif not query:
        st.warning("📝 Опишите, кому нужен подарок")
    else:
        with st.spinner("🤔 Генерация идей... (может занять 2-3 минуты)"):
            result, error = call_api(query, feedback=None, iteration=0)
            
            if error:
                st.error(error)
            elif result:
                ideas = result.get("ideas", [])
                st.session_state.current_ideas = ideas
                st.session_state.iteration = result.get("iteration", 0)
                
                st.session_state.messages.append({
                    "role": "user",
                    "content": query[:200] + ("..." if len(query) > 200 else "")
                })
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Нашёл {len(ideas)} идей для подарка"
                })
                
                st.success(f"✅ Найдено {len(ideas)} идей!")
                st.rerun()

# Отображение идей
if st.session_state.current_ideas:
    st.divider()
    
    # Статус
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.markdown(f'<span class="badge badge-success">🎁 {len(st.session_state.current_ideas)} идей</span>', unsafe_allow_html=True)
    with col_info2:
        st.markdown(f'<span class="badge badge-info">🔄 Итерация {st.session_state.iteration}/3</span>', unsafe_allow_html=True)
    with col_info3:
        if st.session_state.iteration < 3:
            st.markdown('<span class="badge badge-info">💬 Можно уточнить</span>', unsafe_allow_html=True)
    
    # Идеи
    for i, idea in enumerate(st.session_state.current_ideas, 1):
        display_gift_card(idea, i)
    
    # Форма уточнения
    if st.session_state.iteration < 3:
        st.markdown("""
        <div class="feedback-card">
            <h4>💬 Уточните подбор</h4>
            <p style="color:#666; font-size:0.9rem;">Напишите, что добавить или убрать</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("feedback_form"):
            feedback = st.text_area(
                "",
                placeholder="Например: убери технику, добавь идеи для кулинарии",
                height=80,
                label_visibility="collapsed"
            )
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button("🔄 Уточнить", use_container_width=True)
            with col_btn2:
                reset = st.form_submit_button("🗑️ Начать заново", use_container_width=True)
            
            if submitted and feedback:
                with st.spinner("🎯 Уточняю подбор... (может занять 2-3 минуты)"):
                    result, error = call_api(
                        st.session_state.query,
                        feedback=feedback,
                        iteration=st.session_state.iteration + 1
                    )
                    
                    if error:
                        st.error(error)
                    elif result:
                        ideas = result.get("ideas", [])
                        st.session_state.current_ideas = ideas
                        st.session_state.iteration = result.get("iteration", st.session_state.iteration + 1)
                        
                        st.session_state.messages.append({
                            "role": "user",
                            "content": f"📝 Уточнение: {feedback[:150]}"
                        })
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": f"Обновил подбор, теперь {len(ideas)} идей"
                        })
                        
                        st.success(f"✅ Обновлено! {len(ideas)} новых идей")
                        st.rerun()
            
            if reset:
                st.session_state.messages = []
                st.session_state.current_ideas = []
                st.session_state.iteration = 0
                st.session_state.query = ""
                st.session_state.debug_info = []
                st.rerun()

# История чата
if st.session_state.messages:
    with st.expander("💬 История диалога", expanded=False):
        display_chat()

# Футер
st.divider()
st.caption("🎁 GiftGenius • AI-помощник для подбора подарков")