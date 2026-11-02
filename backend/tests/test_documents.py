"""Upload validation, processing and document lifecycle (TC-01 … TC-03)."""
from __future__ import annotations

from app.core.config import settings
from tests.conftest import SAMPLE_NOTES, upload_text


def test_upload_txt_is_chunked_and_indexed(client, auth, ready_document):
    assert ready_document["status"] == "ready"
    assert ready_document["page_count"] == 1
    assert ready_document["chunk_count"] >= 1
    assert ready_document["embedding_model"]

    listed = client.get("/api/v1/documents", headers=auth["headers"]).json()
    assert [doc["id"] for doc in listed] == [ready_document["id"]]


def test_upload_pdf_is_extracted(client, auth, pdf_bytes):
    response = client.post(
        "/api/v1/documents/upload",
        headers=auth["headers"],
        files={"file": ("chapter.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    document = response.json()

    detail = client.get(f"/api/v1/documents/{document['id']}", headers=auth["headers"]).json()
    assert detail["status"] == "ready", detail.get("error_message")
    assert detail["page_count"] == 1
    assert detail["chunk_count"] >= 1


def test_upload_rejects_unsupported_extension(client, auth):
    response = upload_text(client, auth["headers"], content="hello", filename="notes.md")
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_rejects_spoofed_pdf(client, auth):
    response = client.post(
        "/api/v1/documents/upload",
        headers=auth["headers"],
        files={"file": ("broken.pdf", b"not really a pdf", "application/pdf")},
    )
    assert response.status_code == 400


def test_upload_rejects_empty_file(client, auth):
    response = client.post(
        "/api/v1/documents/upload",
        headers=auth["headers"],
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_rejects_oversized_file(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_size_mb", 0)
    response = upload_text(client, auth["headers"], content=SAMPLE_NOTES)
    assert response.status_code == 400
    assert "limit" in response.json()["detail"].lower()


def test_failed_pdf_processing_reports_status(client, auth, pdf_bytes, monkeypatch):
    # Simulate a corrupt document that passes the magic-byte check but cannot be parsed.
    corrupt = b"%PDF-1.4\n" + b"0" * 200
    response = client.post(
        "/api/v1/documents/upload",
        headers=auth["headers"],
        files={"file": ("corrupt.pdf", corrupt, "application/pdf")},
    )
    assert response.status_code == 201
    detail = client.get(
        f"/api/v1/documents/{response.json()['id']}", headers=auth["headers"]
    ).json()
    assert detail["status"] == "failed"
    assert detail["error_message"]


def test_delete_document_removes_chunks(client, auth, ready_document):
    response = client.delete(
        f"/api/v1/documents/{ready_document['id']}", headers=auth["headers"]
    )
    assert response.status_code == 204
    assert client.get("/api/v1/documents", headers=auth["headers"]).json() == []


def test_search_endpoint_returns_page_metadata(client, auth, ready_document):
    response = client.post(
        f"/api/v1/documents/{ready_document['id']}/search",
        headers=auth["headers"],
        json={"query": "third normal form transitive dependency", "top_k": 3},
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert results
    top = results[0]
    assert top["document_id"] == ready_document["id"]
    assert top["page_number"] >= 1
    assert "normal" in top["content"].lower()
    assert isinstance(top["similarity"], float)


def test_search_requires_ready_document(client, auth, monkeypatch):
    # Force a processing state by patching the background processing away.
    from app.api import documents as documents_api

    monkeypatch.setattr(documents_api, "process_document", lambda _doc_id: None)
    response = upload_text(client, auth["headers"])
    document = response.json()
    search = client.post(
        f"/api/v1/documents/{document['id']}/search",
        headers=auth["headers"],
        json={"query": "database"},
    )
    assert search.status_code == 409
