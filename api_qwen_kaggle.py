from fastapi import FastAPI
from pydantic import BaseModel
import logging
import time

# Новый импорт: API теперь смотрит на rag_pipeline_qwen_kaggle.py
from rag_pipeline_qwen_kaggle import generate_gifts, gift_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GiftGenius API | Qwen on Kaggle | Agent Pipeline",
    version="1.0.0",
)


class Request(BaseModel):
    description: str


class Response(BaseModel):
    ideas: list[str]
    processing_time: float | None = None
    status: str = "success"
    graph_mode: str | None = None


@app.get("/")
def root():
    return {
        "message": "🎁 GiftGenius API | Qwen on Kaggle | Agent Pipeline",
        "status": "healthy",
        "endpoints": ["/health", "/generate", "/debug"],
    }


@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": time.time()}


@app.post("/generate", response_model=Response)
def generate(request: Request):
    start = time.time()
    logger.info("📨 Запрос: %s", request.description)

    try:
        result = gift_agent(request.description, verbose=False)

        if result.get("status") == "needs_clarification":
            return {
                "ideas": [f"Уточните: {result.get('questions', 'Недостаточно данных для подбора подарка.')}"] ,
                "processing_time": time.time() - start,
                "status": "needs_clarification",
                "graph_mode": result.get("graph_mode"),
            }

        return {
            "ideas": result.get("ideas", []),
            "processing_time": time.time() - start,
            "status": result.get("status", "success"),
            "graph_mode": result.get("graph_mode"),
        }
    except Exception as e:
        logger.exception("❌ Ошибка generate")
        return {
            "ideas": [f"Ошибка: {e}"],
            "processing_time": time.time() - start,
            "status": "error",
            "graph_mode": None,
        }


@app.post("/debug")
def debug(request: Request):
    start = time.time()
    logger.info("🛠 DEBUG запрос: %s", request.description)

    try:
        result = gift_agent(request.description, verbose=True)
        result["processing_time"] = time.time() - start
        return result
    except Exception as e:
        logger.exception("❌ Ошибка debug")
        return {
            "status": "error",
            "error": str(e),
            "processing_time": time.time() - start,
        }


# Для локального запуска внутри ноутбука / контейнера:
# !uvicorn api_qwen_kaggle:app --host 0.0.0.0 --port 8000
