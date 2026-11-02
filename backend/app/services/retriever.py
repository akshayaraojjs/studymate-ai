"""Vector retrieval with ownership enforcement.

When the caller supplies the query text, results are re-ranked with a small lexical
signal on the section heading: a passage whose heading is named in the query (for
example "Explain Database Fundamentals" and "Chapter 1 Database Fundamentals") is
promoted, and partial heading overlap adds a modest boost. Pure semantic search then
no longer loses an exact chapter title to a chunk that merely talks about the topic.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Document, DocumentChunk
from app.db.session import engine
from app.db.types import pgvector_available

_WORD_RE = re.compile(r"[a-z0-9]+")
_TITLE_PREFIX_RE = re.compile(
    r"^\s*(?:chapter|unit|section|part|module|lesson|topic)\s+[\divxlcdm]+\b[.:)\s-]*",
    re.IGNORECASE,
)
_NUMBER_PREFIX_RE = re.compile(r"^\s*\d+(?:\.\d+)*\b[.:)\s-]*")

_STOPWORDS = frozenset(
    """
    a an the and or of in on for to from with about what which how why who is are was were
    does do did explain describe define tell me my our your this that these those it its can
    could would should please according notes note document documents material chapter
    """.split()
)

_FULL_TITLE_SCORE = 0.9
_MAX_PARTIAL_BOOST = 0.2


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_name: str
    chunk_index: int
    content: str
    page_number: int
    section_title: str | None
    similarity: float

    @property
    def label(self) -> str:
        title = self.section_title or self.document_name
        return f"{title}, page {self.page_number}"


def owned_ready_documents(db: Session, user_id: str, document_ids: list[str] | None = None) -> list[Document]:
    """Return documents owned by the user; unknown/foreign ids are silently dropped."""
    query = db.query(Document).filter(
        Document.user_id == user_id, Document.status == "ready"
    )
    if document_ids:
        query = query.filter(Document.id.in_(document_ids))
    return query.order_by(Document.created_at.asc()).all()


def search_chunks(
    db: Session,
    user_id: str,
    query_embedding: list[float],
    document_ids: list[str] | None = None,
    top_k: int | None = None,
    query_text: str | None = None,
) -> list[RetrievedChunk]:
    """Cosine-similarity search scoped to the user's own documents.

    ``query_text`` is optional; when given, heading matches are folded into the
    returned similarity so callers rank on a hybrid relevance score.
    """
    limit = top_k or settings.retrieval_top_k
    allowed_ids = [doc.id for doc in owned_ready_documents(db, user_id, document_ids)]
    if not allowed_ids:
        return []

    # Fetch extra candidates so a heading match outside the vector top-k can still win.
    fetch_limit = min(limit * 3, 50) if query_text else limit
    if engine.dialect.name == "postgresql" and pgvector_available():
        results = _search_postgres(user_id, allowed_ids, query_embedding, fetch_limit)
    else:
        # SQLite, or PostgreSQL without pgvector: vectors are JSON text, scored here.
        results = _search_python(db, user_id, allowed_ids, query_embedding, fetch_limit)

    if query_text and results:
        results = _rerank_with_headings(results, query_text, limit)
    return results


def _significant_terms(text: str) -> set[str]:
    return {
        word
        for word in _WORD_RE.findall(text.lower())
        if len(word) > 2 and word not in _STOPWORDS
    }


def _heading_phrase(section_title: str | None) -> list[str]:
    """Strip 'Chapter 1' style prefixes, keeping the meaningful heading words."""
    if not section_title:
        return []
    text = _TITLE_PREFIX_RE.sub("", section_title)
    text = _NUMBER_PREFIX_RE.sub("", text)
    words = _WORD_RE.findall(text.lower())
    return [word for word in words if word not in _STOPWORDS]


def _same_word(left: str, right: str) -> bool:
    if left == right:
        return True
    # Tolerate simple inflections (join / joins, index / indexes) without a stemmer.
    return len(left) >= 4 and len(right) >= 4 and left[:5] == right[:5]


def _heading_score(section_title: str | None, query_text: str) -> float:
    """1.0 when the query names the heading, softer values for partial overlap."""
    heading = _heading_phrase(section_title)
    if not heading:
        return 0.0

    query_words = _WORD_RE.findall(query_text.lower())
    if all(any(_same_word(word, candidate) for candidate in query_words) for word in heading):
        return 1.0

    heading_terms = _significant_terms(" ".join(heading))
    query_terms = _significant_terms(query_text)
    if not heading_terms or not query_terms:
        return 0.0
    matched = sum(1 for term in heading_terms if any(_same_word(term, q) for q in query_terms))
    return matched / len(heading_terms)


def _rerank_with_headings(
    results: list[RetrievedChunk], query_text: str, limit: int
) -> list[RetrievedChunk]:
    for chunk in results:
        score = _heading_score(chunk.section_title, query_text)
        if score >= 1.0:
            chunk.similarity = max(chunk.similarity, _FULL_TITLE_SCORE)
        elif score > 0:
            chunk.similarity = min(1.0, chunk.similarity + _MAX_PARTIAL_BOOST * score)
    results.sort(key=lambda chunk: chunk.similarity, reverse=True)
    return results[:limit]


def _search_postgres(
    user_id: str,
    document_ids: list[str],
    query_embedding: list[float],
    limit: int,
) -> list[RetrievedChunk]:
    vector_literal = "[" + ",".join(f"{v:.6f}" for v in query_embedding) + "]"
    statement = text(
        """
        SELECT c.id AS chunk_id, c.document_id, d.filename AS document_name,
               c.chunk_index, c.content, c.page_number, c.section_title,
               1 - (c.embedding <=> CAST(:query_vector AS vector)) AS similarity
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.user_id = :user_id
          AND d.status = 'ready'
          AND c.document_id IN :document_ids
          AND c.embedding IS NOT NULL
        ORDER BY c.embedding <=> CAST(:query_vector AS vector)
        LIMIT :limit
        """
    ).bindparams(bindparam("document_ids", expanding=True))

    with engine.connect() as conn:
        rows = conn.execute(
            statement,
            {
                "user_id": user_id,
                "document_ids": document_ids,
                "query_vector": vector_literal,
                "limit": limit,
            },
        ).mappings()
        results = [
            RetrievedChunk(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                document_name=row["document_name"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                page_number=row["page_number"],
                section_title=row["section_title"],
                similarity=float(row["similarity"]),
            )
            for row in rows
        ]
    return results


def _search_python(
    db: Session,
    user_id: str,
    document_ids: list[str],
    query_embedding: list[float],
    limit: int,
) -> list[RetrievedChunk]:
    """Cosine similarity in NumPy for backends without a vector column."""
    rows = (
        db.query(DocumentChunk, Document.filename)
        .join(Document, Document.id == DocumentChunk.document_id)
        .filter(
            Document.user_id == user_id,
            Document.status == "ready",
            DocumentChunk.document_id.in_(document_ids),
            DocumentChunk.embedding.isnot(None),
        )
        .all()
    )
    if not rows:
        return []

    query = np.asarray(query_embedding, dtype=np.float32)
    query_norm = np.linalg.norm(query) or 1.0
    scored: list[tuple[float, DocumentChunk, str]] = []
    for chunk, filename in rows:
        vector = np.asarray(chunk.embedding, dtype=np.float32)
        denominator = (np.linalg.norm(vector) or 1.0) * query_norm
        score = float(np.dot(vector, query) / denominator)
        scored.append((score, chunk, filename))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_name=filename,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            page_number=chunk.page_number,
            section_title=chunk.section_title,
            similarity=score,
        )
        for score, chunk, filename in scored[:limit]
    ]
