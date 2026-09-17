"""API and browser-UI tests for the cv-rag-tailor service."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
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
    for needle in ("CV Tailor", "Job description", "Tailor my CV", "Download DOCX", "Download PDF"):
        assert needle in body


def test_tailor_upload_with_text_file_returns_grounded_result() -> None:
    res = client.post(
        "/tailor-upload",
        data={"job_description": JD},
        files={"cv": ("base_cv.txt", CV.encode(), "text/plain")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["tailored_cv"].startswith("TARGETED SUMMARY")
    assert body["match_report"]["score"] > 0
    assert body["evidence"], "expected retrieved evidence"
    assert body["change_log"], "expected at least one evidence-backed change"
    for change in body["change_log"]:
        assert change["evidence_ids"], "every change must cite evidence"


def test_tailor_upload_preserves_fabrication_guards() -> None:
    jd = JD + "\nMust have hands-on Kubernetes and 12 years of distributed systems experience."
    res = client.post(
        "/tailor-upload",
        data={"job_description": jd},
        files={"cv": ("base_cv.txt", CV.encode(), "text/plain")},
    )
    assert res.status_code == 200
    body = res.json()
    # Missing JD terms surface as gaps and are never inserted into the tailored CV.
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


def test_tailor_upload_extracts_docx(tmp_path: Path) -> None:
    import docx

    document = docx.Document()
    for line in CV.splitlines():
        if line.strip():
            document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)

    res = client.post(
        "/tailor-upload",
        data={"job_description": JD},
        files={
            "cv": (
                "cv.docx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert res.status_code == 200
    assert res.json()["match_report"]["score"] > 0


def test_export_docx_returns_a_valid_word_file() -> None:
    payload = {
        "tailored_cv": "TARGETED SUMMARY\nBuilt test tooling.\n\nEXPERIENCE\nQA Engineer",
        "score": 75,
        "matched": ["playwright"],
        "missing": ["kubernetes"],
    }
    res = client.post("/export/docx", json=payload)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert res.headers["content-disposition"].endswith('filename="tailored-cv.docx"')
    archive = zipfile.ZipFile(io.BytesIO(res.content))
    assert "word/document.xml" in archive.namelist()
    text = archive.read("word/document.xml").decode()
    assert "Built test tooling." in text
    assert "75/100" in text


def test_export_pdf_returns_a_real_pdf() -> None:
    payload = {
        "tailored_cv": "TARGETED SUMMARY\nBuilt test tooling.\n\nEXPERIENCE\nQA Engineer",
        "score": 60,
        "matched": ["ci"],
        "missing": ["docker"],
    }
    res = client.post("/export/pdf", json=payload)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF-")
    assert len(res.content) > 1000


def test_export_rejects_blank_cv() -> None:
    res = client.post("/export/pdf", json={"tailored_cv": "short"})
    assert res.status_code == 422
