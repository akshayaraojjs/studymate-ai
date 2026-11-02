"""StudyMate AI FastAPI application."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import auth, chat, documents, study  # noqa: F401
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import engine, init_db
from app.services.document_processor import DocumentProcessingError
from app.services.embeddings import embedding_model_name
from app.services.llm_service import llm_service

logger = get_logger(__name__)

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    init_db()
    logger.info("StudyMate AI starting (env=%s, db=%s)", settings.app_env, "postgres" if settings.is_postgres else "sqlite")
    if not llm_service.available:
        logger.warning("GROQ_API_KEY is not set: chat and study tools will return 503.")
    logger.info("Embedding model: %s", embedding_model_name())
    yield


app = FastAPI(
    title="StudyMate AI",
    description="RAG + agentic study assistant grounded in the learner's own material.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(DocumentProcessingError)
async def document_error_handler(_request: Request, exc: DocumentProcessingError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


@app.get("/health", tags=["system"])
def health() -> dict:
    database_ok = True
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover
        database_ok = False
    return {
        "status": "ok" if database_ok else "degraded",
        "database": "ok" if database_ok else "unavailable",
        "database_backend": "postgresql" if settings.is_postgres else "sqlite",
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "llm_configured": llm_service.available,
        "embedding_model": embedding_model_name(),
    }


app.include_router(auth.auth_router, prefix=API_PREFIX)
app.include_router(documents.documents_router, prefix=API_PREFIX)
app.include_router(chat.chat_router, prefix=API_PREFIX)
app.include_router(study.study_router, prefix=API_PREFIX)
