"""Document schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    file_type: str
    status: str
    page_count: int
    chunk_count: int
    size_bytes: int
    embedding_model: str = ""
    error_message: str | None = None
    created_at: datetime


class DocumentSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class ChunkOut(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    page_number: int
    section_title: str | None
    content: str
    similarity: float


class DocumentSearchResponse(BaseModel):
    query: str
    results: list[ChunkOut]
