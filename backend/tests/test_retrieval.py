"""Retrieval quality, chunk metadata and chunker behaviour."""
from __future__ import annotations

from app.db.session import SessionLocal
from app.services.chunker import PageText, chunk_pages, clean_text, estimate_tokens, looks_like_heading
from app.services.embeddings import embed_query
from app.services.retriever import search_chunks


def test_chunker_preserves_page_and_section_metadata():
    pages = [
        PageText(
            page_number=3,
            text=(
                "Chapter 3 Normalization\n\n"
                + "Normalization reduces redundancy. " * 80
                + "\n\nSecond normal form removes partial dependencies. "
                + "This sentence is repeated to build enough content. " * 40
            ),
        )
    ]
    chunks = chunk_pages(pages, chunk_size_tokens=200, overlap_tokens=40)
    assert len(chunks) >= 2
    assert all(chunk.page_number == 3 for chunk in chunks)
    assert chunks[0].section_title == "Chapter 3 Normalization"
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.token_count > 0 for chunk in chunks)


def test_chunker_uses_overlap_between_chunks():
    text = "\n\n".join(f"Paragraph {index} " + "content " * 30 for index in range(8))
    chunks = chunk_pages([PageText(1, text)], chunk_size_tokens=150, overlap_tokens=60)
    assert len(chunks) > 1
    # Consecutive chunks share the trailing text of the previous chunk.
    assert chunks[0].content[-40:] in chunks[1].content


def test_each_chapter_page_becomes_its_own_chunk():
    pages = [
        PageText(
            page_number=index,
            text=(
                f"Chapter {index} Topic {index}\n"
                + f"Body text for chapter {index}. " * 12
            ),
        )
        for index in range(1, 5)
    ]
    chunks = chunk_pages(pages, chunk_size_tokens=700, overlap_tokens=100)
    assert len(chunks) == 4
    assert [chunk.page_number for chunk in chunks] == [1, 2, 3, 4]
    assert [chunk.section_title for chunk in chunks] == [
        "Chapter 1 Topic 1",
        "Chapter 2 Topic 2",
        "Chapter 3 Topic 3",
        "Chapter 4 Topic 4",
    ]
    assert all(chunk.content.startswith(f"Chapter {index}") for index, chunk in enumerate(chunks, start=1))


def test_heading_detection_and_clean_text():
    assert looks_like_heading("Chapter 3 Normalization")
    assert looks_like_heading("3.2 Third Normal Form")
    assert looks_like_heading("SQL JOINS")
    assert not looks_like_heading("This is a normal sentence that ends with a period.")

    dirty = "Line one  \r\n\r\n\r\n\r\nLine two\x00 with exam-\r\nple"
    cleaned = clean_text(dirty)
    assert "\x00" not in cleaned
    assert "example" in cleaned
    assert "\n\n\n" not in cleaned


def test_estimate_tokens_scales_with_length():
    assert estimate_tokens("") == 1
    assert estimate_tokens("a" * 400) == 100


def test_vector_search_prefers_relevant_chunk(client, auth, ready_document):
    db = SessionLocal()
    try:
        results = search_chunks(
            db=db,
            user_id=auth["user"]["id"],
            query_embedding=embed_query("cross join cartesian product"),
            document_ids=[ready_document["id"]],
            top_k=3,
        )
    finally:
        db.close()
    assert results
    assert "cross join" in results[0].content.lower()
    assert results[0].page_number == 1


def test_vector_search_is_scoped_to_user(client, auth, ready_document):
    import uuid

    db = SessionLocal()
    try:
        results = search_chunks(
            db=db,
            user_id=str(uuid.uuid4()),
            query_embedding=embed_query("normalization"),
            document_ids=[ready_document["id"]],
        )
    finally:
        db.close()
    assert results == []


def _upload_notes(client, headers, content: str, filename: str) -> dict:
    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (filename, content.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 201, response.text
    document = response.json()
    for _ in range(20):
        detail = client.get(f"/api/v1/documents/{document['id']}", headers=headers).json()
        document = detail
        if detail["status"] != "processing":
            break
    assert document["status"] == "ready", document.get("error_message")
    return document


def test_exact_heading_query_ranks_the_matching_section_first(client, auth):
    """'Explain Database Fundamentals' must retrieve that chapter, not a lookalike chunk."""
    content = (
        "Chapter 1 Database Fundamentals\n\n"
        "A database is an organised collection of structured data. A relational model "
        "stores rows and columns. SQL defines schemas.\n\n"
        "Chapter 2 Joins\n\n" + "Database fundamentals tables rows columns SQL relational data. " * 30
    )
    document = _upload_notes(client, auth["headers"], content, "headings.txt")

    query = "Explain Database Fundamentals"
    db = SessionLocal()
    try:
        results = search_chunks(
            db=db,
            user_id=auth["user"]["id"],
            query_embedding=embed_query(query),
            document_ids=[document["id"]],
            top_k=5,
            query_text=query,
        )
    finally:
        db.close()

    assert results
    assert results[0].section_title == "Chapter 1 Database Fundamentals"
    assert results[0].similarity >= 0.9


def test_vector_search_ignores_unselected_documents(client, auth, ready_document):
    db = SessionLocal()
    try:
        results = search_chunks(
            db=db,
            user_id=auth["user"]["id"],
            query_embedding=embed_query("normalization"),
            document_ids=["00000000-0000-0000-0000-000000000000"],
        )
    finally:
        db.close()
    assert results == []
