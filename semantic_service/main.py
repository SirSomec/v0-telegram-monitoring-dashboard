"""
Сервис эмбеддингов для семантического поиска. Запускается в отдельном контейнере.
Загружает sentence-transformers и отдаёт эмбеддинги по HTTP.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    model_name = os.getenv("SEMANTIC_MODEL_NAME", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
    from sentence_transformers import SentenceTransformer
    _MODEL = SentenceTransformer(model_name)
    return _MODEL


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Опционально: прогрев модели при старте (раскомментировать при желании)
    # if os.getenv("SEMANTIC_PRELOAD", "").strip().lower() in ("1", "true", "yes"):
    #     _get_model()
    yield
    global _MODEL
    _MODEL = None


app = FastAPI(title="Semantic Embeddings", lifespan=lifespan)


class EmbedRequest(BaseModel):
    texts: list[str]


class EmbedResponse(BaseModel):
    vectors: list[list[float]]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/embed", response_model=EmbedResponse)
def embed(request: EmbedRequest):
    if not request.texts:
        return EmbedResponse(vectors=[])
    texts = [t for t in request.texts if (t or "").strip()]
    if not texts:
        return EmbedResponse(vectors=[])
    try:
        model = _get_model()
        vectors = model.encode(texts, convert_to_numpy=True)
        return EmbedResponse(vectors=[v.tolist() for v in vectors])
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
