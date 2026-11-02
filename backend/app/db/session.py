"""SQLAlchemy engine, session factory and schema bootstrap."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    pass


def _build_engine():
    url = settings.resolved_database_url
    kwargs: dict = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
    return create_engine(url, **kwargs)


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


if settings.resolved_database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _record):  # pragma: no cover
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_pgvector() -> bool:
    """Enable pgvector when the server ships it; report whether vectors are native."""
    if not settings.resolved_database_url.startswith("postgresql"):
        return False
    from app.db.types import pgvector_available

    if not pgvector_available():
        logger.warning(
            "pgvector is not installed on this PostgreSQL server: embeddings are stored as "
            "text and similarity is computed in Python. Install pgvector and re-index to use "
            "native vector search."
        )
        return False
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("pgvector extension is enabled")
        return True
    except Exception as exc:  # pragma: no cover - depends on the database
        logger.warning("Could not enable pgvector (%s); using text vectors", exc)
        return False


def init_db() -> None:
    """Create tables and, when pgvector is usable, the vector index."""
    from app.db import models  # noqa: F401  (register mappers)

    native_vectors = _ensure_pgvector()
    Base.metadata.create_all(bind=engine)

    if native_vectors:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding "
                        "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
                    )
                )
        except Exception as exc:  # pragma: no cover - depends on pgvector version
            logger.warning("Could not create HNSW index: %s", exc)
    logger.info(
        "Database schema ready (%s, vectors=%s)",
        "postgresql" if settings.is_postgres else "sqlite",
        "pgvector" if native_vectors else "python",
    )
