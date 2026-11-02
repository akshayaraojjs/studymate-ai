"""Study endpoints: quiz and chapter summary.

These call the same internal tools the chat agent uses, so studio behaviour and
agent behaviour stay consistent.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agent.tools import ToolContext
from app.agent.tools.quiz_generator import generate_quiz_tool
from app.agent.tools.summarizer import summarize_chapter_tool
from app.api.deps import get_current_user
from app.core.ratelimit import enforce_rate_limit
from app.db.models import User
from app.db.session import get_db
from app.schemas.study import QuizRequest, QuizResponse, SummaryRequest, SummaryResponse

study_router = APIRouter(prefix="/study", tags=["study"])


@study_router.post("/quiz", response_model=QuizResponse)
async def create_quiz(
    payload: QuizRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuizResponse:
    enforce_rate_limit(f"study:{current_user.id}", limit=15)
    ctx = ToolContext(
        db=db, user_id=current_user.id, document_ids=payload.document_ids
    )
    result = await generate_quiz_tool.handler(
        {
            "topic": payload.topic,
            "document_ids": payload.document_ids,
            "num_questions": payload.num_questions,
        },
        ctx,
    )
    if ctx.quiz is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result.content)
    return QuizResponse(**ctx.quiz)


@study_router.post("/summary", response_model=SummaryResponse)
async def create_summary(
    payload: SummaryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SummaryResponse:
    enforce_rate_limit(f"study:{current_user.id}", limit=15)
    ctx = ToolContext(db=db, user_id=current_user.id, document_ids=payload.document_ids)
    result = await summarize_chapter_tool.handler(
        {
            "chapter": payload.chapter,
            "document_ids": payload.document_ids,
            "page_start": payload.page_start,
            "page_end": payload.page_end,
        },
        ctx,
    )
    if ctx.summary is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result.content)
    return SummaryResponse(**ctx.summary)
