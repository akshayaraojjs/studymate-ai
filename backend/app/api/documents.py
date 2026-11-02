"""Document upload, listing, deletion and passage search."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.logging import get_logger
from app.core.ratelimit import enforce_rate_limit
from app.db.models import Document, User
from app.db.session import get_db
from app.schemas.documents import (
    ChunkOut,
    DocumentOut,
    DocumentSearchRequest,
    DocumentSearchResponse,
)
from app.services.document_processor import (
    DocumentProcessingError,
    process_document,
    safe_display_name,
    validate_upload,
)
from app.services.embeddings import embed_query
from app.services.retriever import search_chunks

logger = get_logger(__name__)
documents_router = APIRouter(prefix="/documents", tags=["documents"])


def _owned_document(db: Session, user: User, document_id: str) -> Document:
    """Fetch a document only if the authenticated user owns it."""
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user.id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return document


@documents_router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentOut:
    enforce_rate_limit(f"upload:{current_user.id}", limit=20)

    content = await file.read(settings.max_upload_bytes + 1)
    try:
        file_type = validate_upload(file.filename, content, file.content_type)
    except DocumentProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    stored_filename = f"{uuid.uuid4().hex}.{file_type}"
    destination = settings.upload_dir / stored_filename
    destination.write_bytes(content)

    document = Document(
        user_id=current_user.id,
        filename=safe_display_name(file.filename),
        stored_filename=stored_filename,
        file_type=file_type,
        size_bytes=len(content),
        status="processing",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(process_document, document.id)
    logger.info("Queued document %s for processing (%s bytes)", document.id, len(content))
    return DocumentOut.model_validate(document)


@documents_router.get("", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[DocumentOut]:
    documents = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return [DocumentOut.model_validate(document) for document in documents]


@documents_router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentOut:
    return DocumentOut.model_validate(_owned_document(db, current_user, document_id))


@documents_router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    document = _owned_document(db, current_user, document_id)
    stored_path = settings.upload_dir / document.stored_filename
    db.delete(document)
    db.commit()
    try:
        stored_path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete stored file for document %s", document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@documents_router.post("/{document_id}/search", response_model=DocumentSearchResponse)
def search_document(
    document_id: str,
    payload: DocumentSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentSearchResponse:
    document = _owned_document(db, current_user, document_id)
    if document.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is still processing or failed to process.",
        )
    chunks = search_chunks(
        db=db,
        user_id=current_user.id,
        query_embedding=embed_query(payload.query),
        document_ids=[document.id],
        top_k=payload.top_k,
        query_text=payload.query,
    )
    return DocumentSearchResponse(
        query=payload.query,
        results=[
            ChunkOut(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_name=chunk.document_name,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                content=chunk.content,
                similarity=round(chunk.similarity, 4),
            )
            for chunk in chunks
        ],
    )
