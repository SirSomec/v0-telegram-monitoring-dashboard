"""
Провайдер эмбеддингов для семантического сопоставления ключевых слов (общая тема сообщения, мультиязычность).
- SEMANTIC_PROVIDER=http + SEMANTIC_SERVICE_URL: запросы к отдельному контейнеру (рекомендуется в проде).
- SEMANTIC_PROVIDER=local: локальная модель sentence-transformers в процессе бэкенда.
Настройки берутся из parser_settings (админка) или из env.
При недоступности возвращается None — парсер считает семантические ключи как точные.
"""
from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request

_SENTENCE_TRANSFORMER = None
_THRESHOLD = 0.55  # порог по умолчанию для лучшего охвата темы

# Модель по умолчанию: понимание общей темы, EN+RU и др. (сильнее MiniLM)
_DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


def _config_str(key: str, env_fallback: str = "") -> str:
    """Значение настройки: из БД (parser_settings), иначе из env, иначе env_fallback."""
    try:
        from parser_config import get_parser_setting_str
        v = get_parser_setting_str(key, "")
        if (v or "").strip():
            return v.strip()
    except ImportError:
        pass
    return (os.getenv(key) or env_fallback).strip()


def _config_float(key: str, default: float) -> float:
    """Число с плавающей точкой: из БД или env. Для SEMANTIC_SIMILARITY_THRESHOLD допустим только 0–1."""
    try:
        from parser_config import get_parser_setting_float
        v = get_parser_setting_float(key, default)
        if key == "SEMANTIC_SIMILARITY_THRESHOLD" and (v < 0 or v > 1):
            return default
        return v
    except ImportError:
        pass
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        t = float(raw)
        if key == "SEMANTIC_SIMILARITY_THRESHOLD":
            return t if 0 <= t <= 1 else default
        return t
    except ValueError:
        pass
    return default


def _get_threshold() -> float:
    global _THRESHOLD
    t = _config_float("SEMANTIC_SIMILARITY_THRESHOLD", 0.55)
    _THRESHOLD = t
    return _THRESHOLD


def _service_url() -> str | None:
    url = _config_str("SEMANTIC_SERVICE_URL").rstrip("/")
    return url or None


def _use_http() -> bool:
    provider = _config_str("SEMANTIC_PROVIDER").lower()
    return provider == "http" or _service_url() is not None


def _embed_http_timeout() -> float:
    """Таймаут в секундах для HTTP-запроса к сервису эмбеддингов."""
    try:
        from parser_config import get_parser_setting_int
        v = get_parser_setting_int("SEMANTIC_HTTP_TIMEOUT", 60)
        return max(10, min(300, v))
    except ImportError:
        pass
    try:
        v = int(os.getenv("SEMANTIC_HTTP_TIMEOUT", "60").strip())
        return max(10, min(300, v))
    except ValueError:
        return 60.0


def _embed_via_http(texts: list[str]) -> list[list[float]] | None:
    url = _service_url()
    if not url or not texts:
        return None
    base = url.replace("/embed", "").replace("/health", "")
    embed_url = f"{base}/embed"
    timeout = _embed_http_timeout()
    req = urllib.request.Request(
        embed_url,
        data=json.dumps({"texts": texts}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("vectors")
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError, TimeoutError, OSError):
        return None


def _load_model():
    """Ленивая загрузка локальной модели. При ошибке возвращает None."""
    global _SENTENCE_TRANSFORMER
    if _SENTENCE_TRANSFORMER is not None:
        return _SENTENCE_TRANSFORMER
    provider = _config_str("SEMANTIC_PROVIDER").lower()
    if provider != "local":
        return None
    try:
        from sentence_transformers import SentenceTransformer

        model_name = _config_str("SEMANTIC_MODEL_NAME", _DEFAULT_MODEL) or _DEFAULT_MODEL
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


def embed_with_config(
    texts: list[str],
    *,
    service_url: str | None = None,
    timeout_sec: float = 60,
    provider: str = "http",
    model_name: str | None = None,
) -> list[list[float]] | None:
    """
    Эмбеддинги с явным конфигом (без вызова parser_config/БД).
    Для вызова из фонового потока executor — конфиг передаётся из основного потока.
    """
    if not texts:
        return None
    use_http = (provider or "").strip().lower() == "http" or bool((service_url or "").strip())
    if use_http and (service_url or "").strip():
        url = (service_url or "").rstrip("/")
        if not url:
            return None
        base = url.replace("/embed", "").replace("/health", "")
        embed_url = f"{base}/embed"
        timeout = max(10, min(300, timeout_sec))
        req = urllib.request.Request(
            embed_url,
            data=json.dumps({"texts": texts}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("vectors")
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError, TimeoutError, OSError):
            return None
    if (provider or "").strip().lower() == "local":
        name = (model_name or "").strip() or _DEFAULT_MODEL
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(name)
            vectors = model.encode(texts, convert_to_numpy=True)
            return [v.tolist() for v in vectors]
        except Exception:
            return None
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

    def update(
        self,
        keyword_texts: list[str],
        embed_func: None = None,  # callable: (list[str]) -> list[list[float]] | None
    ) -> None:
        """Обновить кэш: вычислить эмбеддинги для переданных текстов (только недостающие).
        embed_func: если задан, вызывается вместо embed() (для фонового потока без доступа к БД)."""
        if not keyword_texts:
            return
        to_compute = [t for t in keyword_texts if (t or "").strip() and (t or "").strip() not in self._cache]
        if not to_compute:
            return
        vectors = (embed_func(to_compute) if embed_func else embed(to_compute))
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
