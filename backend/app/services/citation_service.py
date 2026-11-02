"""Citation building and validation.

A citation may only reference a chunk that was actually retrieved for the
response, so source identifiers are assigned by the backend, never invented by
the model.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from app.services.retriever import RetrievedChunk

_MARKER_RE = re.compile(r"\[(\d{1,2})\]")
_SNIPPET_LIMIT = 420


@dataclass
class Citation:
    number: int
    chunk_id: str
    document_id: str
    document_name: str
    page_number: int
    section_title: str | None
    snippet: str
    similarity: float

    def to_dict(self) -> dict:
        return asdict(self)


def build_citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    """Number evidence in retrieval order, de-duplicating repeated chunks."""
    citations: list[Citation] = []
    seen: set[str] = set()
    for chunk in chunks:
        if chunk.chunk_id in seen:
            continue
        seen.add(chunk.chunk_id)
        snippet = chunk.content.strip()
        if len(snippet) > _SNIPPET_LIMIT:
            snippet = snippet[:_SNIPPET_LIMIT].rstrip() + "…"
        citations.append(
            Citation(
                number=len(citations) + 1,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_name=chunk.document_name,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                snippet=snippet,
                similarity=round(chunk.similarity, 4),
            )
        )
    return citations


def cited_numbers(answer: str, citations: list[Citation]) -> list[int]:
    valid = {c.number for c in citations}
    numbers = {int(match) for match in _MARKER_RE.findall(answer)}
    return sorted(n for n in numbers if n in valid)


def finalize(answer: str, citations: list[Citation]) -> tuple[list[Citation], list[Citation]]:
    """Return (all sources offered, citations actually referenced by the answer)."""
    referenced_numbers = cited_numbers(answer, citations)
    referenced = [c for c in citations if c.number in referenced_numbers]
    return citations, referenced


def strip_invalid_markers(answer: str, citations: list[Citation]) -> str:
    """Remove citation markers the model invented (no matching source)."""
    valid = {c.number for c in citations}

    def replace(match: re.Match[str]) -> str:
        return match.group(0) if int(match.group(1)) in valid else ""

    return _MARKER_RE.sub(replace, answer)
