"""Study tool schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class QuizRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    document_ids: list[str] = Field(default_factory=list)
    num_questions: int = Field(default=5, ge=3, le=8)


class QuizQuestion(BaseModel):
    id: int
    question: str
    options: list[str]
    correct_option: int
    explanation: str
    source_numbers: list[int] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class QuizResponse(BaseModel):
    attempt_id: str | None = None
    topic: str
    questions: list[QuizQuestion]
    citations: list[dict] = Field(default_factory=list)


class SummaryRequest(BaseModel):
    chapter: str | None = Field(default=None, max_length=200)
    document_ids: list[str] = Field(default_factory=list)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)


class SummaryResponse(BaseModel):
    chapter: str
    markdown: str
    citations: list[dict] = Field(default_factory=list)


class ToolErrorResponse(BaseModel):
    detail: str
