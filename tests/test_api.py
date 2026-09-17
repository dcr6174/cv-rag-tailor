"""API and browser-UI tests for the cv-rag-tailor service."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from cv_tailor.api import app

client = TestClient(app)

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
JD = (SAMPLES / "job_description.txt").read_text()
CV = (SAMPLES / "base_cv.txt").read_text()


def test_home_serves_the_ui_page() -> None:
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    body = res.text
    for needle in ("CV RAG Tailor", "Job description", "Tailor my CV", "Download DOCX", "Download PDF",
                   "Requirement coverage", "Batch rank", "parseability", "Verbatim", "Rephrased"):
        assert needle in body


def test_tailor_endpoint_returns_v03_shape() -> None:
    res = client.post("/tailor", json={"job_description": JD, "base_cv": CV, "page_budget": 1})
    assert res.status_code == 200
    body = res.json()
    assert body["tailored_cv"].startswith("CHANDRA") or "TARGETED SUMMARY" in body["tailored_cv"]
    assert "score" not in str(body.keys()).lower()
    cov = body["coverage"]
    assert cov["hard_total"] >= 1
    for row in cov["rows"]:
        assert row["status"] in {"covered", "partial", "missing"}
    assert body["parseability"], "expected parseability checks"
    for unit in body["tailored_units"]:
        assert unit["provenance"] in {"verbatim", "rephrased", "reframed"}
        assert unit["evidence_ids"], "every tailored line must cite evidence"


def test_tailor_upload_with_text_file() -> None:
    res = client.post(
        "/tailor-upload",
        data={"job_description": JD, "page_budget": "2"},
        files={"cv": ("base_cv.txt", CV.encode(), "text/plain")},
    )
    assert res.status_code == 200
    assert res.json()["page_budget"] == 2


def test_tailor_upload_preserves_fabrication_guards() -> None:
    jd = JD + "\nMust have hands-on Kubernetes and 12 years of distributed systems experience."
    res = client.post(
        "/tailor-upload",
        data={"job_description": jd},
        files={"cv": ("base_cv.txt", CV.encode(), "text/plain")},
    )
    assert res.status_code == 200
    body = res.json()
    assert "kubernetes" in [g.lower() for g in body["gaps"]]
    assert "kubernetes" not in body["tailored_cv"].lower()


def test_tailor_upload_rejects_unsupported_file_type() -> None:
    res = client.post(
        "/tailor-upload",
        data={"job_description": JD},
        files={"cv": ("photo.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")},
    )
    assert res.status_code == 422
    assert "Unsupported file type" in res.json()["detail"]


def test_tailor_upload_rejects_empty_file() -> None:
    res = client.post(
        "/tailor-upload",
        data={"job_description": JD},
        files={"cv": ("empty.txt", b"", "text/plain")},
    )
    assert res.status_code == 422


def test_tailor_upload_rejects_short_text() -> None:
    res = client.post(
        "/tailor-upload",
        data={"job_description": JD},
        files={"cv": ("tiny.txt", b"too short", "text/plain")},
    )
    assert res.status_code == 422


def test_rank_endpoint_orders_results() -> None:
    res = client.post("/rank", json={
        "base_cv": CV,
        "job_descriptions": [
            "We need a Kubernetes and Terraform expert with 10 years of distributed systems experience.",
            JD,
        ],
    })
    assert res.status_code == 200
    ranked = res.json()["ranked"]
    assert ranked[0]["index"] == 1
    assert ranked[0]["coverage_ratio"] >= ranked[1]["coverage_ratio"]


def test_rank_endpoint_validates_input() -> None:
    res = client.post("/rank", json={"base_cv": CV, "job_descriptions": ["short"]})
    assert res.status_code == 422


def test_export_docx_returns_a_real_word_file() -> None:
    res = client.post("/export/docx", json={
        "tailored_cv": CV, "hard_covered": 1, "hard_total": 2,
        "preferred_covered": 0, "preferred_total": 0,
        "matched": ["python"], "missing": ["kubernetes"],
    })
    assert res.status_code == 200
    payload = res.content
    assert zipfile.is_zipfile(io.BytesIO(payload))
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        xml = zf.read("word/document.xml").decode()
    assert "Requirement coverage" in xml
    assert "kubernetes" in xml  # reported as a gap


def test_export_pdf_returns_a_real_pdf() -> None:
    res = client.post("/export/pdf", json={
        "tailored_cv": CV, "hard_covered": 1, "hard_total": 2,
        "matched": ["python"], "missing": [],
    })
    assert res.status_code == 200
    assert res.content.startswith(b"%PDF")


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_samples() -> None:
    body = client.get("/samples").json()
    assert "CHANDRA" in body["base_cv"] and len(body["job_description"]) > 20
