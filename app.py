import streamlit as st
import requests
import time
import re
import urllib.parse

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
    
    st.markdown("---")
    st.markdown("### 🔧 Отладка")
    if st.button("🧪 Показать формат ответа"):
        st.session_state["show_debug"] = True

st.subheader("📝 Опишите человека")

default_value = st.session_state.get("example", "")
description = st.text_area(
    "Введите описание:",
    value=default_value,
    placeholder="Например: парень 25 лет программист любит кофе",
    height=100
)

def extract_gift_title(idea_text):
    """Извлекает название подарка из текста идеи"""
    # Ищем строку с ПОДАРОК:
    title_match = re.search(r'ПОДАРОК:\s*([^\n]+)', idea_text)
    if title_match:
        title = title_match.group(1).strip()
        # Убираем звездочки, кавычки и эмодзи
        title = re.sub(r'[*"`]', '', title)
        # Убираем информацию о цене если есть
        title = re.sub(r'\$.*?\$|💰.*', '', title).strip()
        return title
    return None

def extract_gift_description(idea_text):
    """Извлекает описание подарка"""
    description_parts = []
    
    # Ищем все важные секции
    sections = ['ПОЧЕМУ:', 'МОМЕНТ:', 'ЧЕМ НЕ БАНАЛЬНО:']
    
    for section in sections:
        section_match = re.search(f'{section}\s*([^\n]+)', idea_text)
        if section_match:
            description_parts.append(f"• {section_match.group(1).strip()}")
    
    return "\n\n".join(description_parts) if description_parts else None

def create_market_links(product_name):
    """Создает ссылки на маркетплейсы по названию товара"""
    if not product_name:
        return []
    
    # Очищаем название
    clean_name = product_name.strip()
    
    # Кодируем для URL
    encoded_wb = urllib.parse.quote(clean_name)
    encoded_ya = urllib.parse.quote(clean_name).replace('%20', '+')
    encoded_ozon = urllib.parse.quote(clean_name)
    
    # Создаем ссылки
    links = [
        {
            "name": "Wildberries",
            "url": f"https://www.wildberries.ru/catalog/0/search.aspx?search={encoded_wb}",
            "color": "#9b59b6",
            "icon": "🛍️"
        },
        {
            "name": "Яндекс Маркет",
            "url": f"https://market.yandex.ru/search?text={encoded_ya}",
            "color": "#f1c40f",
            "icon": "🎯"
        },
        {
            "name": "Ozon",
            "url": f"https://www.ozon.ru/search/?text={encoded_ozon}",
            "color": "#3498db",
            "icon": "📦"
        }
    ]
    
    return links

def extract_price_info(idea_text):
    """Извлекает информацию о цене если есть"""
    price_match = re.search(r'💰\s*([^\n]+)', idea_text)
    if price_match:
        return price_match.group(1).strip()
    return None

def display_gift_idea(idea_text, index):
    """Отображает идею подарка с созданными ссылками"""
    
    # Извлекаем информацию
    title = extract_gift_title(idea_text)
    description = extract_gift_description(idea_text)
    price_info = extract_price_info(idea_text)
    
    if not title:
        title = f"Идея подарка #{index}"
    
    # Создаем ссылки на основе названия
    market_links = create_market_links(title)
    
    # Отображаем карточку
    st.markdown(f'<div class="gift-card">', unsafe_allow_html=True)
    
    # Заголовок
    st.markdown(f'<div class="gift-title">🎁 {index}. {title}</div>', unsafe_allow_html=True)
    
    # Информация о цене (если есть)
    if price_info and price_info != "Цена не найдена":
        st.markdown(f'<div class="price-tag">💰 {price_info}</div>', unsafe_allow_html=True)
    
    # Описание
    if description:
        st.markdown(f'<div class="gift-description">{description}</div>', unsafe_allow_html=True)
    
    # Ссылки на маркетплейсы
    if market_links:
        st.markdown('<div class="links"><b>🔗 Где купить:</b></div>', unsafe_allow_html=True)
        
        # Создаем колонки для ссылок
        cols = st.columns(len(market_links))
        
        for idx, link in enumerate(market_links):
            with cols[idx]:
                # Создаем красивую кнопку-ссылку
                button_html = f'''
                    <a href="{link['url']}" target="_blank" class="market-button" 
                       style="background: {link['color']};">
                        {link['icon']} {link['name']}
                    </a>
                '''
                st.markdown(button_html, unsafe_allow_html=True)
    
    # Если нет ссылок, показываем сообщение
    elif title:
        st.markdown('<div class="links"><b>🔍 Поиск на маркетплейсах:</b></div>', unsafe_allow_html=True)
        cols = st.columns(3)
        
        # Wildberries
        with cols[0]:
            wb_url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={urllib.parse.quote(title)}"
            st.markdown(f'<a href="{wb_url}" target="_blank" class="market-button" style="background: #9b59b6;">🛍️ Wildberries</a>', unsafe_allow_html=True)
        
        # Яндекс Маркет
        with cols[1]:
            ya_url = f"https://market.yandex.ru/search?text={urllib.parse.quote(title).replace('%20', '+')}"
            st.markdown(f'<a href="{ya_url}" target="_blank" class="market-button" style="background: #f1c40f;">🎯 Яндекс Маркет</a>', unsafe_allow_html=True)
        
        # Ozon
        with cols[2]:
            ozon_url = f"https://www.ozon.ru/search/?text={urllib.parse.quote(title)}"
            st.markdown(f'<a href="{ozon_url}" target="_blank" class="market-button" style="background: #3498db;">📦 Ozon</a>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

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
            
            # Показываем отладку если нужно
            if st.session_state.get("show_debug", False):
                with st.expander("📊 Отладка - сырой ответ API"):
                    st.json(result)
                    if ideas:
                        st.markdown("### Первая идея (сырой текст):")
                        st.code(ideas[0])
            
            # Отображаем каждую идею
            for i, idea in enumerate(ideas, 1):
                display_gift_idea(idea, i)
                st.markdown("---")
            
        else:
            st.error(f"❌ Ошибка API: {response.status_code}")
            if response.status_code == 502:
                st.error("""
                **Ошибка 502: Bad Gateway**
                
                Возможные причины:
                1. Сервер в Kaggle не запущен
                2. Сервер упал из-за ошибки
                3. Закончилось время сессии Kaggle
                
                **Решение:**
                1. Перейдите в Kaggle ноутбук
                2. Перезапустите все ячейки
                3. Проверьте новый URL в ngrok
                """)
            
    except requests.exceptions.ConnectionError:
        st.error("❌ Ошибка подключения к серверу. Проверьте URL и запущен ли сервер в Kaggle")
    except requests.exceptions.Timeout:
        st.error("❌ Таймаут ожидания ответа от сервера")
    except Exception as e:
        st.error(f"❌ Ошибка: {str(e)}")
    finally:
        progress_bar.empty()
        status_text.empty()

# Добавляем информацию о статусе API внизу страницы
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("🎁 GiftGenius v2.0")
with col2:
    if 'API_URL' in locals():
        st.caption(f"🔗 API: {API_URL.split('/')[2]}")
with col3:
    st.caption("💡 Нажмите ❤️ если нравится")