from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str
    vectorstore_path: str
    chunks_path: str
    database_url: str | None
    redis_url: str | None
    celery_broker_url: str | None
    celery_result_backend: str | None
    groq_model_name: str | None
    groq_api_key_present: bool
    langsmith_project: str | None
    langsmith_tracing_enabled: bool
    cors_origins: tuple[str, ...]


def _parse_origins(value: str | None) -> tuple[str, ...]:
    if not value:
        return ("http://localhost:5173", "http://127.0.0.1:5173")
    return tuple(origin.strip() for origin in value.split(",") if origin.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    langsmith_api_key_present = bool(os.getenv("LANGSMITH_API_KEY"))
    langsmith_tracing_requested = os.getenv("LANGSMITH_TRACING", "true").strip().lower()
    langsmith_tracing_v2_requested = os.getenv("LANGSMITH_TRACING_V2", "true").strip().lower()
    langsmith_enabled = (
        langsmith_api_key_present
        and langsmith_tracing_requested in {"1", "true", "yes", "on"}
        and langsmith_tracing_v2_requested in {"1", "true", "yes", "on"}
    )

    return Settings(
        app_name=os.getenv("APP_NAME", "Acme Company Assistant API"),
        vectorstore_path=os.getenv("VECTORSTORE_PATH", "artifacts/faiss_index"),
        chunks_path=os.getenv("CHUNKS_PATH", "artifacts/chunks.jsonl"),
        database_url=os.getenv("DATABASE_URL"),
        redis_url=os.getenv("REDIS_URL"),
        celery_broker_url=os.getenv("CELERY_BROKER_URL"),
        celery_result_backend=os.getenv("CELERY_RESULT_BACKEND"),
        groq_model_name=os.getenv("GROQ_MODEL_NAME"),
        groq_api_key_present=bool(os.getenv("GROQ_API_KEY")),
        langsmith_project=os.getenv("LANGSMITH_PROJECT", "acme-company-assistant-dev")
        if langsmith_enabled
        else None,
        langsmith_tracing_enabled=langsmith_enabled,
        cors_origins=_parse_origins(os.getenv("BACKEND_CORS_ORIGINS")),
    )


def path_exists(path: str) -> bool:
    return Path(path).exists()
