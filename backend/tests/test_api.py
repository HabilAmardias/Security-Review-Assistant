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


def test_frameworks_endpoint_removed(container):
    with _client(container) as client:
        res = client.get("/api/frameworks")
        assert res.status_code == 404


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
        # Non-PDF content named .pdf is detected by content and decoded as text.
        frd = b"FRD text with payment data and OAuth authentication"
        nfrd = b"NFRD internet-facing portal, PII data, POJK compliance"
        res = client.post(
            "/api/reviews",
            files={
                "frd": ("frd.pdf", frd, "application/pdf"),
                "nfrd": ("nfrd.pdf", nfrd, "application/pdf"),
            },
        )
        assert res.status_code == 200
        assert res.json()["frd_name"] == "frd.pdf"

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


def test_delete_review(container):
    from ase_security_review.domain.enums import ReviewStatus

    review = container.review_usecase.create_review("f.pdf", "text", "n.pdf", "text")
    with _client(container) as client:
        res = client.delete(f"/api/reviews/{review.id}")
        assert res.status_code == 200
        assert client.get(f"/api/reviews/{review.id}").status_code == 404
        # deleting again -> 404
        assert client.delete(f"/api/reviews/{review.id}").status_code == 404


def test_create_review_with_markdown(container):
    with _client(container) as client:
        frd_md = b"# FRD\n\n## Features\n1. OAuth2 login\n2. Payment checkout"
        nfrd_md = b"# NFRD\n\n- Internet-facing\n- PCI DSS"
        res = client.post(
            "/api/reviews",
            files={
                "frd": ("frd.md", frd_md, "text/markdown"),
                "nfrd": ("nfrd.md", nfrd_md, "text/markdown"),
            },
        )
        assert res.status_code == 200
        review = client.get(f"/api/reviews/{res.json()['id']}").json()
        assert "# FRD" in review["frd_text"]
        assert "PCI DSS" in review["nfrd_text"]


def test_text_named_pdf_is_decoded_as_text(container):
    # content decides parsing, not the filename
    with _client(container) as client:
        res = client.post(
            "/api/reviews",
            files={
                "frd": ("frd.pdf", b"# Not a real pdf, just markdown", "text/plain"),
                "nfrd": ("nfrd.txt", b"# NFRD plain text", "text/plain"),
            },
        )
        assert res.status_code == 200
        review = client.get(f"/api/reviews/{res.json()['id']}").json()
        assert "Not a real pdf" in review["frd_text"]


def test_real_pdf_named_md_is_parsed_as_pdf(container, sample_pdf):
    with _client(container) as client:
        payload = sample_pdf.read_bytes()
        res = client.post(
            "/api/reviews",
            files={
                "frd": ("frd.md", payload, "text/markdown"),
                "nfrd": ("nfrd.txt", b"# NFRD", "text/plain"),
            },
        )
        assert res.status_code == 200
        review = client.get(f"/api/reviews/{res.json()['id']}").json()
        assert "Pentest Selection SOP" in review["frd_text"]


def test_markdown_bom_is_stripped(container):
    with _client(container) as client:
        frd_md = b"\xef\xbb\xbf# FRD with BOM\n- feature"
        res = client.post(
            "/api/reviews",
            files={
                "frd": ("frd.md", frd_md, "text/markdown"),
                "nfrd": ("nfrd.txt", b"# NFRD", "text/plain"),
            },
        )
        assert res.status_code == 200
        review = client.get(f"/api/reviews/{res.json()['id']}").json()
        assert not review["frd_text"].startswith("\ufeff")
        assert review["frd_text"].startswith("# FRD")


def test_update_exposure_patch(container):
    review = container.review_usecase.create_review(
        "f.pdf", "Payment checkout.", "n.pdf", "Portal.", detected_exposure="internet-facing"
    )
    review = container.review_usecase.run_review(review.id)
    with _client(container) as client:
        res = client.patch(f"/api/reviews/{review.id}/exposure", json={"exposure": "internal"})
        assert res.status_code == 200
        body = res.json()
        assert body["exposure_override"] == "internal"
        assert body["facts"]["exposure"] == "internal"

        # clearing the override
        res = client.patch(f"/api/reviews/{review.id}/exposure", json={"exposure": None})
        assert res.status_code == 200
        assert res.json()["exposure_override"] is None
        # back to detected exposure
        assert res.json()["facts"]["exposure"] == "internet-facing"


def test_update_change_scope_patch(container):
    review = container.review_usecase.create_review(
        "f.pdf", "Payment checkout.", "n.pdf", "Internet-facing portal.", detected_exposure="internet-facing"
    )
    review = container.review_usecase.run_review(review.id)
    with _client(container) as client:
        res = client.patch(f"/api/reviews/{review.id}/change-scope", json={"change_scope": "limited_change"})
        assert res.status_code == 200
        body = res.json()
        assert body["change_scope_override"] == "limited_change"
        assert body["facts"]["change_scope"] == "limited_change"

        # clearing the override falls back to the FRD/LLM value
        res = client.patch(f"/api/reviews/{review.id}/change-scope", json={"change_scope": None})
        assert res.status_code == 200
        assert res.json()["change_scope_override"] is None


def test_mark_stale_running_failed(container):
    review = container.review_usecase.create_review("f.pdf", "text", "n.pdf", "text")
    assert container.reviews.get(review.id).status.value == "running"
    assert container.reviews.mark_stale_running_failed() >= 1
    stale = container.reviews.get(review.id)
    assert stale.status.value == "failed"
    assert "restart" in stale.error


def test_set_final_decision(container):
    review = container.review_usecase.create_review("f.pdf", "text", "n.pdf", "text")
    with _client(container) as client:
        payload = {
            "requires_pentest": False,
            "test_level": "dast",
            "classification_reason": "human override",
            "risk_factors": [],
            "scope": {"in_scope": ["web"]},
        }
        res = client.patch(f"/api/reviews/{review.id}/decision", json=payload)
        assert res.status_code == 200
        assert res.json()["final_decision"]["test_level"] == "dast"
