"""Shared tool types."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.services.citation_service import Citation, build_citations
from app.services.retriever import RetrievedChunk


@dataclass
class ToolContext:
    db: Session
    user_id: str
    document_ids: list[str]
    evidence: list[RetrievedChunk] = field(default_factory=list)
    external_sources: list[dict[str, Any]] = field(default_factory=list)
    calculations: list[dict[str, str]] = field(default_factory=list)
    quiz: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)
    tool_names: list[str] = field(default_factory=list)

    def add_evidence(self, chunks: list[RetrievedChunk]) -> list[Citation]:
        known = {chunk.chunk_id for chunk in self.evidence}
        for chunk in chunks:
            if chunk.chunk_id not in known:
                self.evidence.append(chunk)
                known.add(chunk.chunk_id)
        return build_citations(self.evidence)

    @property
    def citations(self) -> list[Citation]:
        return build_citations(self.evidence)

    def citation_number(self, chunk_id: str) -> int | None:
        for citation in self.citations:
            if citation.chunk_id == chunk_id:
                return citation.number
        return None


@dataclass
class ToolResult:
    content: str
    ok: bool = True
    summary: str = ""


ToolHandler = Callable[[dict[str, Any], ToolContext], Awaitable[ToolResult]]


@dataclass
class AgentTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    activity: str

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
