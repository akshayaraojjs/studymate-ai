"""Streaming chat and conversation history endpoints."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agent.orchestrator import stream_agent_response
from app.api.deps import get_current_user
from app.core.logging import get_logger
from app.core.ratelimit import enforce_rate_limit
from app.db.models import Conversation, Message, User
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ConversationOut, MessageOut
from app.services.llm_service import llm_service

logger = get_logger(__name__)
chat_router = APIRouter(tags=["chat"])


@chat_router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enforce_rate_limit(f"chat:{current_user.id}", limit=20)
    if not llm_service.available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI provider is not configured. Set GROQ_API_KEY and restart the server.",
        )

    async def event_stream():
        try:
            async for event in stream_agent_response(
                db=db,
                user_id=current_user.id,
                message=payload.message.strip(),
                document_ids=payload.document_ids,
                conversation_id=payload.conversation_id,
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception:
            logger.exception("Chat stream failed")
            error_event = {
                "type": "error",
                "message": "The assistant could not complete this response. Please retry.",
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'saved': False})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@chat_router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[ConversationOut]:
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
        .all()
    )
    return [ConversationOut.model_validate(conversation) for conversation in conversations]


@chat_router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def conversation_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MessageOut]:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    results: list[MessageOut] = []
    for message in messages:
        citations: list[dict] = []
        if message.citations_json:
            try:
                parsed = json.loads(message.citations_json)
                if isinstance(parsed, list):
                    citations = parsed
            except json.JSONDecodeError:
                citations = []
        results.append(
            MessageOut(
                id=message.id,
                role=message.role,
                content=message.content,
                tool_name=message.tool_name,
                citations=citations,
                created_at=message.created_at,
            )
        )
    return results
