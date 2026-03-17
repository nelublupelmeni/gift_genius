import os
import re
import urllib.parse

import requests
import streamlit as st

st.set_page_config(
    page_title="GiftGenius",
    page_icon="🎁",
    layout="centered"
)

DEFAULT_BASE_URL = os.getenv("GIFTGENIUS_BASE_URL", "https://lucio-lucent-jurnee.ngrok-free.dev")
default_base = st.session_state.get("base_url", DEFAULT_BASE_URL).rstrip("/")

st.markdown("""
<style>
    .stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #FF4B4B 0%, #FF8C42 100%);
        color: white;
        font-weight: bold;
        border: none;
    }
    .gift-card {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        margin: 15px 0;
        border-left: 5px solid #ff4b4b;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .gift-title {
        color: #ff4b4b;
        font-size: 1.3em;
        font-weight: bold;
        margin-bottom: 15px;
        border-bottom: 2px dashed #ff4b4b;
        padding-bottom: 8px;
    }
    .gift-description {
        color: #666;
        margin: 15px 0;
        padding: 15px;
        background: white;
        border-radius: 8px;
        font-style: italic;
        line-height: 1.6;
    }
    .links {
        margin-top: 20px;
        padding-top: 15px;
        border-top: 2px solid #ff4b4b;
    }
    .market-button {
        display: inline-block;
        width: 100%;
        padding: 12px 5px;
        color: white;
        text-decoration: none;
        border-radius: 25px;
        text-align: center;
        font-weight: bold;
        font-size: 14px;
        transition: all 0.3s;
        border: none;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        margin: 5px 0;
    }
    .market-button:hover {
        transform: scale(1.05);
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }
    .price-tag {
        background: linear-gradient(90deg, #FF4B4B 0%, #FF8C42 100%);
        color: white;
        padding: 3px 10px;
        border-radius: 15px;
        font-size: 0.9em;
        display: inline-block;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

st.title("🎁 GiftGenius")
st.markdown("### AI-помощник для подбора подарков")
st.markdown("#### Локальный Streamlit + Kaggle backend")
st.markdown("---")

with st.sidebar:
    st.header("⚙️ Подключение")
    base_url = st.text_input(
        "Ngrok URL из Kaggle",
        value=default_base,
        help="Вставьте URL вида https://walker-unerasable-will.ngrok-free.dev"
    ).strip().rstrip("/")
    st.session_state["base_url"] = base_url

    API_URL = f"{base_url}/generate"
    HEALTH_URL = f"{base_url}/health"

    st.caption(f"POST: {API_URL}")
    st.caption(f"GET:  {HEALTH_URL}")

    if st.button("🔌 Проверить сервер"):
        try:
            r = requests.get(HEALTH_URL, timeout=10)
            if r.status_code == 200:
                st.success("✅ Kaggle backend отвечает")
            else:
                st.error(f"❌ Ошибка: {r.status_code}")
        except Exception as e:
            st.error(f"❌ Не удалось подключиться: {e}")

    st.markdown("---")
    st.header("ℹ️ О проекте")
    st.write("Локальный интерфейс, генерация идей через Kaggle GPU, ссылки на маркетплейсы строятся локально.")

    st.header("🎯 Примеры")
    examples = [
        "Подруга, 30 лет, йога, веганство, любит читать",
        "Папа, 55 лет, рыбалка, дача, грибы",
        "Коллега, 40 лет, гитарист, любит готовить",
        "Парень, 25 лет, программист, любит кофе и механические клавиатуры",
    ]

    for example in examples:
        if st.button(f"📋 {example[:24]}...", key=example):
            st.session_state["example"] = example

    st.markdown("---")
    if st.button("🧪 Показать сырой ответ"):
        st.session_state["show_debug"] = True


def extract_gift_title(idea_text):
    title_match = re.search(r'ПОДАРОК:\s*([^\n]+)', idea_text)
    if title_match:
        title = title_match.group(1).strip()
        title = re.sub(r'[*"`]', '', title)
        title = re.sub(r'\$.*?\$|💰.*', '', title).strip()
        return title
    return None


def extract_gift_description(idea_text):
    description_parts = []
    sections = ['ПОЧЕМУ:', 'МОМЕНТ:', 'ЧЕМ НЕ БАНАЛЬНО:']
    for section in sections:
        section_match = re.search(rf'{section}\s*([^\n]+)', idea_text)
        if section_match:
            description_parts.append(f"• {section_match.group(1).strip()}")
    return "\n\n".join(description_parts) if description_parts else None


def create_market_links(product_name):
    if not product_name:
        return []
    clean_name = product_name.strip()
    encoded_wb = urllib.parse.quote(clean_name)
    encoded_ya = urllib.parse.quote(clean_name).replace('%20', '+')
    encoded_ozon = urllib.parse.quote(clean_name)
    return [
        {
            "name": "Wildberries",
            "url": f"https://www.wildberries.ru/catalog/0/search.aspx?search={encoded_wb}",
            "color": "#9b59b6",
            "icon": "🛍️",
        },
        {
            "name": "Яндекс Маркет",
            "url": f"https://market.yandex.ru/search?text={encoded_ya}",
            "color": "#f1c40f",
            "icon": "🎯",
        },
        {
            "name": "Ozon",
            "url": f"https://www.ozon.ru/search/?text={encoded_ozon}",
            "color": "#3498db",
            "icon": "📦",
        },
    ]


def extract_price_info(idea_text):
    price_match = re.search(r'💰\s*([^\n]+)', idea_text)
    if price_match:
        return price_match.group(1).strip()
    return None


def display_gift_idea(idea_text, index):
    title = extract_gift_title(idea_text)
    description = extract_gift_description(idea_text)
    price_info = extract_price_info(idea_text)

    if not title:
        title = f"Идея подарка #{index}"

    market_links = create_market_links(title)

    st.markdown('<div class="gift-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="gift-title">🎁 {index}. {title}</div>', unsafe_allow_html=True)

    if price_info and price_info != "Цена не найдена":
        st.markdown(f'<div class="price-tag">💰 {price_info}</div>', unsafe_allow_html=True)

    if description:
        st.markdown(f'<div class="gift-description">{description}</div>', unsafe_allow_html=True)

    if market_links:
        st.markdown('<div class="links"><b>🔗 Где купить:</b></div>', unsafe_allow_html=True)
        cols = st.columns(len(market_links))
        for idx, link in enumerate(market_links):
            with cols[idx]:
                button_html = f'''
                    <a href="{link['url']}" target="_blank" class="market-button"
                       style="background: {link['color']};">
                        {link['icon']} {link['name']}
                    </a>
                '''
                st.markdown(button_html, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


st.subheader("📝 Опишите человека")
default_value = st.session_state.get("example", "")
description = st.text_area(
    "Введите описание:",
    value=default_value,
    placeholder="Например: парень 25 лет, программист, любит кофе и гаджеты",
    height=120,
)

if st.button("🎁 Найти подарки", type="primary", use_container_width=True) and description:
    API_URL = f"{st.session_state['base_url']}/generate"
    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.text("🤔 Генерация идей...")
    progress_bar.progress(25)

    try:
        response = requests.post(
            API_URL,
            json={"description": description},
            timeout=(10, 300),
        )

        progress_bar.progress(75)
        status_text.text("📥 Обработка ответа...")

        if response.status_code == 200:
            result = response.json()
            ideas = result.get("ideas", [])

            progress_bar.progress(100)
            status_text.text("✅ Готово")

            st.success(f"✅ Найдено {len(ideas)} идей")
            st.markdown("---")
            st.subheader("🎁 Ваши идеи подарков")

            if st.session_state.get("show_debug", False):
                with st.expander("📊 Сырой ответ сервера"):
                    st.json(result)
                    if ideas:
                        st.code(ideas[0])

            for i, idea in enumerate(ideas, 1):
                display_gift_idea(idea, i)
                st.markdown("---")
        else:
            st.error(f"❌ Ошибка сервера: {response.status_code}")
            try:
                st.json(response.json())
            except Exception:
                st.text(response.text)

    except requests.exceptions.ConnectionError as e:
        st.error(f"❌ Нет подключения к Kaggle backend.\nДетали: {e}")
    except requests.exceptions.Timeout:
        st.error("❌ Таймаут. Скорее всего Kaggle backend еще грузит модель или запрос слишком длинный.")
    except Exception as e:
        st.error(f"❌ Ошибка: {e}")
    finally:
        progress_bar.empty()
        status_text.empty()

st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("🎁 GiftGenius v6")
with col2:
    base = st.session_state.get("base_url", DEFAULT_BASE_URL)
    if base:
        st.caption(f"🔗 {base.replace('https://', '')}")
with col3:
    st.caption("⚡ Local UI + Kaggle GPU")
