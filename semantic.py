"""
Провайдер эмбеддингов для семантического сопоставления ключевых слов.
- SEMANTIC_PROVIDER=http + SEMANTIC_SERVICE_URL: запросы к отдельному контейнеру (рекомендуется в проде).
- SEMANTIC_PROVIDER=local: локальная модель sentence-transformers в процессе бэкенда.
При недоступности возвращается None — парсер считает семантические ключи как точные.
"""
from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request

_SENTENCE_TRANSFORMER = None
_THRESHOLD = 0.7


def _get_threshold() -> float:
    global _THRESHOLD
    v = os.getenv("SEMANTIC_SIMILARITY_THRESHOLD", "").strip()
    if not v:
        return _THRESHOLD
    try:
        t = float(v)
        if 0 <= t <= 1:
            _THRESHOLD = t
    except ValueError:
        pass
    return _THRESHOLD


def _service_url() -> str | None:
    url = (os.getenv("SEMANTIC_SERVICE_URL") or "").strip().rstrip("/")
    return url or None


def _use_http() -> bool:
    provider = (os.getenv("SEMANTIC_PROVIDER") or "").strip().lower()
    return provider == "http" or _service_url() is not None


def _embed_via_http(texts: list[str]) -> list[list[float]] | None:
    url = _service_url()
    if not url or not texts:
        return None
    base = url.replace("/embed", "").replace("/health", "")
    embed_url = f"{base}/embed"
    req = urllib.request.Request(
        embed_url,
        data=json.dumps({"texts": texts}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("vectors")
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError):
        return None


def _load_model():
    """Ленивая загрузка локальной модели. При ошибке возвращает None."""
    global _SENTENCE_TRANSFORMER
    if _SENTENCE_TRANSFORMER is not None:
        return _SENTENCE_TRANSFORMER
    provider = (os.getenv("SEMANTIC_PROVIDER") or "").strip().lower()
    if provider != "local":
        return None
    try:
        from sentence_transformers import SentenceTransformer

        model_name = os.getenv("SEMANTIC_MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        _SENTENCE_TRANSFORMER = SentenceTransformer(model_name)
        return _SENTENCE_TRANSFORMER
    except Exception:
        return None


def is_semantic_available() -> bool:
    """Проверка: доступен ли провайдер эмбеддингов (локальная модель или HTTP-сервис)."""
    if _use_http():
        url = _service_url()
        if not url:
            return False
        base = url.replace("/embed", "").replace("/health", "")
        try:
            req = urllib.request.Request(f"{base}/health", method="GET")
            with urllib.request.urlopen(req, timeout=5):
                return True
        except (urllib.error.URLError, urllib.error.HTTPError):
            return False
    return _load_model() is not None


def embed(texts: list[str]) -> list[list[float]] | None:
    """
    Возвращает эмбеддинги для списка текстов. При недоступности модели или ошибке — None.
    """
    if not texts:
        return None
    if _use_http():
        return _embed_via_http(texts)
    model = _load_model()
    if model is None:
        return None
    try:
        vectors = model.encode(texts, convert_to_numpy=True)
        return [v.tolist() for v in vectors]
    except Exception:
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Косинусное сходство двух векторов."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def similarity_threshold() -> float:
    """Порог косинусного сходства для совпадения (0.0–1.0)."""
    return _get_threshold()


class KeywordEmbeddingCache:
    """Кэш эмбеддингов семантических ключевых слов. Ключ — текст ключа."""

    def __init__(self) -> None:
        self._cache: dict[str, list[float]] = {}
        self._model_available: bool | None = None

    def update(self, keyword_texts: list[str]) -> None:
        """Обновить кэш: вычислить эмбеддинги для переданных текстов (только недостающие)."""
        if not keyword_texts:
            return
        to_compute = [t for t in keyword_texts if (t or "").strip() and (t or "").strip() not in self._cache]
        if not to_compute:
            return
        vectors = embed(to_compute)
        if vectors is None:
            self._model_available = False
            return
        self._model_available = True
        for text, vec in zip(to_compute, vectors):
            self._cache[text.strip()] = vec

    def get(self, text: str) -> list[float] | None:
        return self._cache.get((text or "").strip())

    def is_available(self) -> bool:
        if self._model_available is None:
            return is_semantic_available()
        return self._model_available is True

    def clear(self) -> None:
        self._cache.clear()
        self._model_available = None
