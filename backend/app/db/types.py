"""Dialect-aware embedding column.

With pgvector installed, PostgreSQL stores a real ``vector(384)`` so similarity search
can use the ``<=>`` operator and an HNSW index. Everywhere else — SQLite, and PostgreSQL
servers that do not ship pgvector — the vector is stored as JSON text and scored in
Python.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core.config import settings

_pgvector_available: bool | None = None


def pgvector_available() -> bool:
    """True when the connected PostgreSQL server has the ``vector`` extension available.

    Probed once per process against the application engine. A failed probe (server down,
    insufficient privileges on ``pg_available_extensions``) simply means text vectors.
    """
    global _pgvector_available
    if _pgvector_available is None:
        from sqlalchemy import text

        try:
            from app.db.session import engine

            with engine.connect() as connection:
                _pgvector_available = (
                    connection.execute(
                        text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
                    ).first()
                    is not None
                )
        except Exception:  # pragma: no cover - depends on the database
            _pgvector_available = False
    return _pgvector_available


def reset_vector_detection() -> None:
    """Forget the cached probe (used by tools that rebuild the engine)."""
    global _pgvector_available
    _pgvector_available = None


class EmbeddingVector(TypeDecorator):
    impl = Text
    cache_ok = True

    def _native(self) -> bool:
        return pgvector_available()

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == "postgresql" and self._native():
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(settings.embedding_dim))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Any, dialect):  # type: ignore[override]
        if value is None:
            return None
        if dialect.name == "postgresql" and self._native():
            return [float(x) for x in value]
        return json.dumps([round(float(x), 6) for x in value])

    def process_result_value(self, value: Any, dialect):  # type: ignore[override]
        if value is None:
            return None
        if dialect.name == "postgresql" and self._native():
            return list(value)
        if isinstance(value, str):
            return json.loads(value)
        return list(value)
