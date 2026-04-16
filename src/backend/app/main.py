from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.app.api.routes import router
from src.backend.app.core.settings import get_settings
from src.backend.app.core.tracing import configure_langsmith
from src.rag.config import validate_embedding_configuration
from src.rag.retriever_backend import resolve_retriever_backend


def create_app() -> FastAPI:
    configure_langsmith()
    validate_embedding_configuration()
    settings = get_settings()
    resolve_retriever_backend(settings.retriever_backend)
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
