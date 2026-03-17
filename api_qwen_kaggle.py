from fastapi import FastAPI
from pydantic import BaseModel
import logging
import time

from rag_pipeline_qwen_kaggle_bm25 import generate_gifts, gift_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GiftGenius API | Qwen3.5-4B 4bit on Kaggle | BM25")


class Request(BaseModel):
    description: str


class Response(BaseModel):
    ideas: list[str]
    processing_time: float | None = None
    status: str = "success"


@app.get("/")
def root():
    return {
        "message": "🎁 GiftGenius v6 | Qwen3.5-4B 4bit on Kaggle | BM25",
        "status": "healthy",
    }


@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": time.time()}


@app.post("/generate", response_model=Response)
def generate(request: Request):
    start = time.time()
    logger.info("📨 Запрос: %s", request.description)
    try:
        ideas = generate_gifts(request.description)
        return {
            "ideas": ideas,
            "processing_time": time.time() - start,
            "status": "success",
        }
    except Exception as e:
        logger.exception("❌ Ошибка generate")
        return {
            "ideas": [f"Ошибка: {e}"],
            "processing_time": time.time() - start,
            "status": "error",
        }


@app.post("/debug")
def debug(request: Request):
    start = time.time()
    try:
        result = gift_agent(request.description, verbose=False)
        result["processing_time"] = time.time() - start
        return result
    except Exception as e:
        logger.exception("❌ Ошибка debug")
        return {"status": "error", "error": str(e), "processing_time": time.time() - start}
