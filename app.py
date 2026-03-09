import streamlit as st
import requests
import time
import re

st.set_page_config(
    page_title="GiftGenius",
    page_icon="🎁",
    layout="centered"
)

# Вставьте ваш актуальный URL из ngrok
API_URL = "https://walker-unerasable-will.ngrok-free.dev/generate"
HEALTH_URL = "https://walker-unerasable-will.ngrok-free.dev/health"

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
    }
    .gift-title {
        color: #ff4b4b;
        font-size: 1.2em;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .gift-description {
        color: #666;
        margin: 10px 0;
        padding: 10px;
        background: white;
        border-radius: 5px;
        font-style: italic;
    }
    .links {
        margin-top: 15px;
        padding-top: 10px;
        border-top: 1px solid #ddd;
    }
    .link-button {
        display: inline-block;
        padding: 8px 15px;
        margin: 3px;
        background: white;
        border: 1px solid #ff4b4b;
        border-radius: 20px;
        text-decoration: none;
        color: #ff4b4b;
        font-size: 0.9em;
        transition: all 0.3s;
    }
    .link-button:hover {
        background: #ff4b4b;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

st.title("🎁 GiftGenius")
st.markdown("### AI-помощник для подбора подарков")
st.markdown("---")

with st.sidebar:
    st.header("ℹ️ О проекте")
    st.write("Поиск подарков по интересам с ссылками на маркетплейсы")
    
    st.header("🎯 Примеры")
    examples = [
        "Подруга, 30 лет, йога, веганство, любит читать",
        "Папа, 55 лет, рыбалка, дача, грибы",
        "Коллега, 40 лет, гитарист, любит готовить"
    ]
    
    for example in examples:
        if st.button(f"📋 {example[:20]}...", key=example):
            st.session_state["example"] = example
    
    if st.button("🔌 Проверить API"):
        try:
            r = requests.get(HEALTH_URL, timeout=5)
            if r.status_code == 200:
                st.success("✅ API работает!")
            else:
                st.error(f"❌ Ошибка: {r.status_code}")
        except:
            st.error("❌ Не удалось подключиться")

st.subheader("📝 Опишите человека")

default_value = st.session_state.get("example", "")
description = st.text_area(
    "Введите описание:",
    value=default_value,
    placeholder="Например: парень 25 лет программист любит кофе",
    height=100
)

def extract_idea_info(idea_text):
    """Извлекает информацию из идеи"""
    lines = idea_text.split('\n')
    
    title = "Идея подарка"
    description = ""
    links = []
    
    for line in lines:
        if 'ПОДАРОК:' in line:
            title = line.replace('ПОДАРОК:', '').strip()
            title = title.strip('*').strip()
        elif 'ПОЧЕМУ:' in line:
            description = line.replace('ПОЧЕМУ:', '').strip()
        elif 'http' in line and ('Wildberries' in line or 'Яндекс' in line or 'Ozon' in line):
            # Извлекаем ссылки
            url_match = re.search(r'\((https?://[^\s]+)\)', line)
            if url_match:
                shop = "Wildberries" if "wildberries" in line else "Яндекс" if "market.yandex" in line else "Ozon"
                links.append((shop, url_match.group(1)))
    
    return title, description, links

if st.button("🎁 Найти подарки", type="primary", use_container_width=True) and description:
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("🤔 Поиск подарков...")
    progress_bar.progress(30)
    
    try:
        response = requests.post(
            API_URL,
            json={"description": description},
            timeout=300
        )
        
        progress_bar.progress(70)
        status_text.text("📥 Обработка...")
        
        if response.status_code == 200:
            result = response.json()
            ideas = result.get("ideas", [])
            
            progress_bar.progress(100)
            status_text.text("✅ Готово!")
            
            st.success(f"✅ Найдено {len(ideas)} идей!")
            st.markdown("---")
            st.subheader("🎁 Ваши идеи подарков:")
            
            for i, idea in enumerate(ideas, 1):
                title, description, links = extract_idea_info(idea)
                
                # Карточка подарка
                st.markdown(f'<div class="gift-card">', unsafe_allow_html=True)
                
                # Заголовок
                st.markdown(f'<div class="gift-title">🎁 {i}. {title}</div>', unsafe_allow_html=True)
                
                # Описание (если есть)
                if description:
                    st.markdown(f'<div class="gift-description">💡 {description}</div>', unsafe_allow_html=True)
                
                # Ссылки
                if links:
                    st.markdown('<div class="links"><b>🔗 Где купить:</b></div>', unsafe_allow_html=True)
                    cols = st.columns(len(links))
                    for idx, (shop, url) in enumerate(links):
                        with cols[idx]:
                            st.markdown(f'<a href="{url}" target="_blank" class="link-button">{shop}</a>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
            
        else:
            st.error(f"❌ Ошибка API: {response.status_code}")
            
    except Exception as e:
        st.error(f"❌ Ошибка: {e}")
    finally:
        progress_bar.empty()
        status_text.empty()