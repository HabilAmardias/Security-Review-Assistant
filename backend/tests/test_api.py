"""HTTP API tests using the FastAPI TestClient with in-memory fakes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ase_security_review.main import create_app


def _client(container):
    app = create_app(container=container)
    return TestClient(app)


def test_health(container):
    with _client(container) as client:
        res = client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


def test_frameworks(container):
    with _client(container) as client:
        res = client.get("/api/frameworks")
        assert res.status_code == 200
        data = res.json()
        assert any(f["key"] == "owasp_asvs" for f in data)


def test_upload_index_unlock_flow(container, sample_pdf):
    with _client(container) as client:
        # upload a plain PDF
        with sample_pdf.open("rb") as fh:
            res = client.post(
                "/api/documents",
                files={"file": ("SOP.pdf", fh, "application/pdf")},
                data={"doc_type": "sop", "mode": "text"},
            )
        assert res.status_code == 200
        doc = res.json()
        assert doc["doc_type"] == "sop"

        # list documents
        docs = client.get("/api/documents").json()
        assert any(d["name"] == "SOP.pdf" for d in docs)

        # delete
        deleted = client.delete(f"/api/documents/{doc['id']}")
        assert deleted.status_code == 200


def test_create_review(container):
    from ase_security_review.domain.enums import DocType
    from ase_security_review.domain.models import Chunk

    container.vectors.upsert_chunks(
        [
            Chunk(
                id="sop:0",
                document_id="sop",
                doc_type=DocType.SOP,
                doc_name="SOP.pdf",
                text="Aplikasi yang memproses data pembayaran wajib penetration test.",
                chunk_index=0,
                embedding=[1.0, 0.0],
            )
        ]
    )

    with _client(container) as client:
        frd = b"FRD text with payment data and OAuth authentication"
        nfrd = b"NFRD internet-facing portal, PII data, POJK compliance"
        res = client.post(
            "/api/reviews",
            files={
                "frd": ("frd.pdf", frd, "application/pdf"),
                "nfrd": ("nfrd.pdf", nfrd, "application/pdf"),
            },
        )
        assert res.status_code == 400  # PDFs with fake content cannot be parsed

        # text-based inputs via temp files are not PDFs -> decode path
        res = client.post(
            "/api/reviews",
            files={
                "frd": ("frd.txt", b"Payment checkout with OAuth login", "text/plain"),
                "nfrd": ("nfrd.txt", b"Internet-facing portal storing PII", "text/plain"),
            },
        )
        assert res.status_code == 200
        review_id = res.json()["id"]

        review = client.get(f"/api/reviews/{review_id}").json()
        assert review["id"] == review_id

        # list reviews
        assert client.get("/api/reviews").json()


def test_set_final_decision(container):
    review = container.review_usecase.create_review("f.pdf", "text", "n.pdf", "text")
    with _client(container) as client:
        payload = {
            "requires_pentest": False,
            "test_level": "dast",
            "classification_reason": "human override",
            "risk_factors": [],
            "scope": {"in_scope": ["web"]},
            "recommended_frameworks": ["owasp_asvs"],
        }
        res = client.patch(f"/api/reviews/{review.id}/decision", json=payload)
        assert res.status_code == 200
        assert res.json()["final_decision"]["test_level"] == "dast"
