"""Upload validation, text extraction, chunking and indexing."""
from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Document, DocumentChunk
from app.db.session import SessionLocal
from app.services.chunker import PageText, chunk_pages, clean_text
from app.services.embeddings import embed_texts, embedding_model_name

logger = get_logger(__name__)

ALLOWED_EXTENSIONS = {".pdf": "pdf", ".txt": "txt"}
MIME_TYPES = {
    "pdf": {"application/pdf", "application/x-pdf", "application/octet-stream"},
    "txt": {"text/plain", "text/markdown", "application/octet-stream", ""},
}


class DocumentProcessingError(Exception):
    """Raised when a file cannot be validated or parsed."""


def safe_display_name(filename: str | None) -> str:
    name = Path(filename or "upload").name.strip() or "upload"
    return name[-200:]


def validate_upload(filename: str | None, content: bytes, content_type: str | None) -> str:
    """Validate extension, size and magic bytes; returns the file type."""
    display_name = safe_display_name(filename)
    extension = Path(display_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise DocumentProcessingError(
            f"Unsupported file type '{extension or 'unknown'}'. Upload a PDF or TXT file."
        )
    file_type = ALLOWED_EXTENSIONS[extension]

    if not content:
        raise DocumentProcessingError("The uploaded file is empty.")
    if len(content) > settings.max_upload_bytes:
        raise DocumentProcessingError(
            f"File exceeds the {settings.max_upload_size_mb} MB upload limit."
        )

    allowed_mimes = MIME_TYPES[file_type]
    if content_type and content_type.split(";")[0].strip() not in allowed_mimes:
        raise DocumentProcessingError(f"Content type '{content_type}' does not match a {file_type} file.")

    if file_type == "pdf" and not content.startswith(b"%PDF"):
        raise DocumentProcessingError("The file does not look like a valid PDF.")
    if file_type == "txt" and b"\x00" in content[:1024]:
        raise DocumentProcessingError("The text file appears to contain binary data.")
    return file_type


def extract_pages(path: Path, file_type: str) -> list[PageText]:
    if file_type == "pdf":
        return _extract_pdf_pages(path)
    return _extract_text_pages(path)


def _extract_pdf_pages(path: Path) -> list[PageText]:
    import pymupdf

    try:
        document = pymupdf.open(path)
    except Exception as exc:  # corrupt or unsupported PDF
        raise DocumentProcessingError("The PDF could not be opened. It may be corrupt.") from exc

    try:
        if document.needs_pass:
            raise DocumentProcessingError("Password-protected PDFs are not supported.")
        if document.page_count == 0:
            raise DocumentProcessingError("The PDF has no pages.")
        if document.page_count > settings.max_upload_pages:
            raise DocumentProcessingError(
                f"PDF has {document.page_count} pages; the limit is {settings.max_upload_pages}."
            )

        pages: list[PageText] = []
        for index, page in enumerate(document, start=1):
            text = clean_text(page.get_text("text") or "")
            if text:
                pages.append(PageText(page_number=index, text=text))
        if not pages:
            raise DocumentProcessingError(
                "No extractable text found. Scanned PDFs need OCR, which this version does not support."
            )
        return pages
    finally:
        document.close()


def _extract_text_pages(path: Path) -> list[PageText]:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - latin-1 always decodes
        raise DocumentProcessingError("The text file encoding could not be detected.")

    text = clean_text(text)
    if not text:
        raise DocumentProcessingError("The text file is empty.")
    return [PageText(page_number=1, text=text)]


def process_document(document_id: str) -> None:
    """Extract, chunk, embed and index a document. Safe to run as a background task."""
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document is None:
            logger.warning("Processing skipped: document %s no longer exists", document_id)
            return

        document.status = "processing"
        document.error_message = None
        db.commit()

        path = settings.upload_dir / document.stored_filename
        if not path.exists():
            raise DocumentProcessingError("Stored file is missing on disk.")

        pages = extract_pages(path, document.file_type)
        chunks = chunk_pages(
            pages,
            chunk_size_tokens=settings.chunk_size_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
        )
        if not chunks:
            raise DocumentProcessingError("No usable text could be chunked from this file.")

        embedding_inputs = [
            f"{chunk.section_title}\n{chunk.content}" if chunk.section_title else chunk.content
            for chunk in chunks
        ]
        vectors = embed_texts(embedding_inputs)
        if len(vectors) != len(chunks):
            raise DocumentProcessingError("Embedding generation returned an unexpected result.")

        db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
        db.add_all(
            [
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    token_count=chunk.token_count,
                    embedding=vector,
                )
                for chunk, vector in zip(chunks, vectors)
            ]
        )

        document.page_count = len(pages)
        document.chunk_count = len(chunks)
        document.embedding_model = embedding_model_name()
        document.status = "ready"
        document.error_message = None
        db.commit()
        logger.info("Indexed document %s (%s chunks)", document.id, len(chunks))
    except DocumentProcessingError as exc:
        db.rollback()
        _mark_failed(db, document_id, str(exc))
    except Exception as exc:  # unexpected: keep the document usable for retry
        db.rollback()
        logger.exception("Failed to process document %s", document_id)
        _mark_failed(db, document_id, f"Processing failed: {exc.__class__.__name__}")
    finally:
        db.close()


def _mark_failed(db, document_id: str, message: str) -> None:
    document = db.get(Document, document_id)
    if document is None:
        return
    document.status = "failed"
    document.error_message = message[:500]
    db.commit()
