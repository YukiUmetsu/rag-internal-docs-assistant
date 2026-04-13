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
    groq_model_name: str | None
    groq_api_key_present: bool
    cors_origins: tuple[str, ...]


def _parse_origins(value: str | None) -> tuple[str, ...]:
    if not value:
        return ("http://localhost:5173", "http://127.0.0.1:5173")
    return tuple(origin.strip() for origin in value.split(",") if origin.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Acme Company Assistant API"),
        vectorstore_path=os.getenv("VECTORSTORE_PATH", "artifacts/faiss_index"),
        chunks_path=os.getenv("CHUNKS_PATH", "artifacts/chunks.jsonl"),
        groq_model_name=os.getenv("GROQ_MODEL_NAME"),
        groq_api_key_present=bool(os.getenv("GROQ_API_KEY")),
        cors_origins=_parse_origins(os.getenv("BACKEND_CORS_ORIGINS")),
    )


def path_exists(path: str) -> bool:
    return Path(path).exists()
