# 🎁 GiftGenius

**AI-помощник для персонализированного подбора подарков** на основе описания человека. Использует RAG (Retrieval-Augmented Generation) с векторным поиском и генерацией идей через Groq API.

## 📋 Содержание
- [Архитектура](#архитектура)
- [Запуск в Kaggle](#запуск-в-kaggle)
- [Запуск локально](#запуск-локально)
- [Получение токенов](#получение-токенов)
- [API Endpoints](#api-endpoints)
- [Структура проекта](#структура-проекта)


## 🚀 Запуск в Kaggle

### 1. Создание нового ноутбука
1. Зайдите на [kaggle.com](https://kaggle.com)
2. Создайте новый ноутбук: **File → New Notebook**
3. Включите GPU: **Settings → Accelerator → NVIDIA T4**

### 2. Загрузка датасета
1. В правой панели нажмите **Add Data**
2. Загрузите датасет: `gift-genius-dataset`
3. Дождитесь загрузки и укажите путь в коде

### 3. Копирование кода

Скопируйте по порядку все ячейки из предоставленного ноутбука:

**Ячейка 1 - установка зависимостей:**
```python
!pip install -q llama-cpp-python sentence-transformers faiss-gpu-cu12 rank-bm25 pandas numpy fastapi uvicorn pyngrok psutil
```

**Ячейка 2 - тест функций ссылок:**
```python
import urllib.parse

def create_wb_link(product_name: str) -> str:
    base_url = "https://www.wildberries.ru/catalog/0/search.aspx?search="
    clean_name = product_name.split(',')[0].strip().strip('"')
    encoded_name = urllib.parse.quote(clean_name)
    return base_url + encoded_name

def create_yamarket_link(product_name: str) -> str:
    base_url = "https://market.yandex.ru/search?text="
    clean_name = product_name.split(',')[0].strip().strip('"')
    encoded_name = urllib.parse.quote(clean_name)
    return base_url + encoded_name

def create_ozon_link(product_name: str) -> str:
    base_url = "https://www.ozon.ru/search/?text="
    clean_name = product_name.split(',')[0].strip().strip('"')
    encoded_name = urllib.parse.quote(clean_name)
    return base_url + encoded_name

def create_all_links(product_name: str) -> dict:
    return {
        "wildberries": create_wb_link(product_name),
        "yamarket": create_yamarket_link(product_name),
        "ozon": create_ozon_link(product_name)
    }

# Пример
product = "Подарочный набор для женского ухода"
links = create_all_links(product)
print(f"Wildberries: {links['wildberries']}")
print(f"Яндекс Маркет: {links['yamarket']}")
print(f"Ozon: {links['ozon']}")
```

**Ячейка 3 - функция создания ссылок:**
```python
def create_search_links_for_idea(idea_title: str) -> str:
    """Создает Markdown-строку со ссылками на поиск идеи на маркетплейсах"""
    clean_title = idea_title.strip().strip('*').strip('"')
    
    wb_link = f"https://www.wildberries.ru/catalog/0/search.aspx?search={urllib.parse.quote(clean_title)}"
    ym_link = f"https://market.yandex.ru/search?text={urllib.parse.quote(clean_title).replace('%20', '+')}"
    ozon_link = f"https://www.ozon.ru/search/?text={urllib.parse.quote(clean_title)}"
    
    return (f"\n\n🔗 **Найти этот подарок:**\n"
            f"  • [Wildberries]({wb_link}) | "
            f"[Яндекс Маркет]({ym_link}) | "
            f"[Ozon]({ozon_link})")
```

**Ячейка 4 - универсальная функция:**
```python
import urllib.parse

def create_market_links(product_name: str) -> dict:
    clean_name = product_name.split(',')[0].strip().strip('"')
    
    encoded_wb = urllib.parse.quote(clean_name)
    encoded_ya = urllib.parse.quote(clean_name).replace('%20', '+')
    encoded_ozon = urllib.parse.quote(clean_name)
    
    return {
        "wildberries": f"https://www.wildberries.ru/catalog/0/search.aspx?search={encoded_wb}",
        "yamarket": f"https://market.yandex.ru/search?text={encoded_ya}",
        "ozon": f"https://www.ozon.ru/search/?text={encoded_ozon}"
    }

# Пример
product = "Кофемашина DeLonghi"
links = create_market_links(product)
print(f"WB: {links['wildberries']}")
print(f"YM: {links['yamarket']}")
print(f"OZ: {links['ozon']}")
```

**Ячейка 5 - rag_pipeline.py:**
```python
%%writefile rag_pipeline.py
# ... (весь код из ноутбука, который мы проверили)
```

**Ячейка 6 - api.py:**
```python
%%writefile api.py
# ... (весь код из ноутбука)
```

**Ячейка 7 - запуск сервера:**
```python
import uvicorn
from threading import Thread
import time
import os

def run_server():
    uvicorn.run("api:app", host="0.0.0.0", port=8000, log_level="info")

os.system("pkill -f uvicorn")
os.system("pkill -f ngrok")
time.sleep(2)

server_thread = Thread(target=run_server)
server_thread.daemon = True
server_thread.start()
time.sleep(3)
print("✅ Сервер запущен")
```

**Ячейка 8 - ngrok:**
```python
from pyngrok import ngrok

ngrok.set_auth_token("ВАШ_NGROK_ТОКЕН")
ngrok.kill()

public_url = ngrok.connect(8000)
print("="*60)
print("🎁 GIFT GENIUS v5 + GROQ API ГОТОВ!")
print("="*60)
print(f"🌐 URL: {public_url}")
print(f"📌 POST {public_url}/generate")
print("="*60)
```

**Ячейка 9 - тест:**
```python
import rag_pipeline

test_query = "Маме 50 лет, любит готовить и читать. Бюджет до 3000 рублей. Не любит сладкое и украшения."
result = rag_pipeline.gift_agent(test_query, verbose=True)

print("\n" + "="*60)
print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ")
print("="*60)
for i, idea in enumerate(result['ideas'], 1):
    print(f"\n--- ИДЕЯ {i} ---")
    print(idea)
```

### 4. Сохранение ноутбука
- **File → Save Version** (можно оставить приватным)

## 💻 Запуск локально

### 1. Установка Python
Скачайте Python 3.12+ с [python.org](https://python.org)

### 2. Клонирование репозитория
```bash
git clone https://github.com/yourusername/gift-genius.git
cd gift-genius
```

### 3. Создание виртуального окружения
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 4. Установка зависимостей
```bash
pip install -r requirements.txt
```

Создайте файл `requirements.txt`:
```
streamlit
requests
urllib3
```

### 5. Настройка `app.py`
Скопируйте предоставленный код `app.py` и замените URL на актуальный из Kaggle:

```python
API_URL = "https://walker-unerasable-will.ngrok-free.dev/generate"
HEALTH_URL = "https://walker-unerasable-will.ngrok-free.dev/health"
```

### 6. Запуск Streamlit
```bash
streamlit run app.py
```

Приложение откроется в браузере по адресу `http://localhost:8501`

## 🔑 Получение токенов

### 1. Groq API Token
1. Зарегистрируйтесь на [console.groq.com](https://console.groq.com)
2. Перейдите в раздел **API Keys**
3. Нажмите **Create API Key**
4. Скопируйте ключ (начинается с `gsk_`)
5. Вставьте в `rag_pipeline.py`:
```python
GROQ_API_KEY = 'gsk_ваш_ключ_сюда'
```

### 2. ngrok Token
1. Зарегистрируйтесь на [ngrok.com](https://ngrok.com)
2. Войдите в аккаунт
3. Перейдите в **Dashboard → Your Authtoken**
4. Скопируйте токен
5. Вставьте в ячейку с ngrok:
```python
ngrok.set_auth_token("ваш_токен_сюда")
```

## 📡 API Endpoints

После запуска сервера в Kaggle доступны следующие endpoints:

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/` | GET | Информация о сервере |
| `/health` | GET | Проверка работоспособности |
| `/generate` | POST | Генерация идей подарков |

### Пример запроса к API
```python
import requests

API_URL = "https://walker-unerasable-will.ngrok-free.dev/generate"

response = requests.post(
    API_URL,
    json={"description": "маме 50 лет, любит готовить"},
    timeout=30
)

print(response.json())
```

## 📁 Структура проекта

```
gift-genius/
├── rag_pipeline.py      # Основная логика RAG и генерации
├── api.py                # FastAPI сервер
├── app.py                # Streamlit интерфейс
├── requirements.txt      # Зависимости
└── README.md             # Документация
```

## ⚙️ Как это работает

1. **Поиск** - По запросу ищутся релевантные товары в базе (FAISS + BM25)
2. **Портрет** - Groq API создает психологический портрет получателя
3. **Анти-предпочтения** - Определяется, что НЕЛЬЗЯ дарить
4. **Генерация** - Groq API генерирует 5 уникальных идей подарков
5. **Ссылки** - Для каждой идеи создаются ссылки на поиск в маркетплейсах

## 🎯 Примеры запросов

- "Подруге 25 лет, любит кошек и читать книги"
- "Папе 55 лет, рыбалка, дача, грибы"
- "Коллеге 40 лет, гитарист, любит готовить"
- "Маме 50 лет, йога, веганство, бюджет до 3000 рублей"

## ❗ Возможные проблемы

### Ошибка 404 в Streamlit
- Проверьте, что URL в `app.py` совпадает с URL из Kaggle
- URL должен заканчиваться на `/generate` и `/health`

### Сервер не запускается в Kaggle
- Перезапустите ядро: `os._exit(00)`
- Выполните все ячейки заново

### Groq API не отвечает
- Проверьте баланс токенов в аккаунте Groq
- Убедитесь, что ключ API правильный

