"""FastAPI service and beginner-friendly browser interface.

Run:  uvicorn cv_tailor.api:app --reload
App:  http://127.0.0.1:8000
Docs: http://127.0.0.1:8000/docs
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from .exports import build_docx, build_pdf
from .extract import ExtractionError, UnsupportedFileError, extract_text
from .models import RankRequest, RankResponse, TailorRequest, TailorResponse
from .pipeline import rank_jobs, tailor_cv

app = FastAPI(title="Grounded CV RAG Tailor", version="0.3.0")

INDEX_HTML = Path(__file__).with_name("static") / "index.html"


class ExportRequest(BaseModel):
    tailored_cv: str = Field(min_length=20)
    hard_covered: int = Field(default=0, ge=0)
    hard_total: int = Field(default=0, ge=0)
    preferred_covered: int = Field(default=0, ge=0)
    preferred_total: int = Field(default=0, ge=0)
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(INDEX_HTML)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/samples")
def samples() -> dict[str, str]:
    sample_dir = Path(__file__).resolve().parents[2] / "samples"
    jd = sample_dir / "job_description.txt"
    cv = sample_dir / "base_cv.txt"
    if not jd.exists() or not cv.exists():
        raise HTTPException(status_code=404, detail="Sample files are not installed.")
    return {"job_description": jd.read_text(), "base_cv": cv.read_text()}


@app.post("/tailor", response_model=TailorResponse)
def tailor(request: TailorRequest) -> TailorResponse:
    return tailor_cv(request.base_cv, request.job_description, request.page_budget)


@app.post("/tailor-upload", response_model=TailorResponse)
async def tailor_upload(
    job_description: str = Form(min_length=20),
    cv: UploadFile = File(...),
    page_budget: int = Form(default=1),
) -> TailorResponse:
    data = await cv.read()
    try:
        base_cv = extract_text(cv.filename or "cv", data)
    except (UnsupportedFileError, ExtractionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if len(base_cv.strip()) < 20:
        raise HTTPException(status_code=422, detail="The CV needs at least 20 characters of text.")
    return tailor_cv(base_cv, job_description, max(1, min(2, page_budget)))


@app.post("/rank", response_model=RankResponse)
def rank(request: RankRequest) -> RankResponse:
    cleaned = [jd for jd in request.job_descriptions if len(jd.strip()) >= 20]
    if not cleaned:
        raise HTTPException(status_code=422, detail="Each job description needs at least 20 characters.")
    return RankResponse(ranked=rank_jobs(request.base_cv, cleaned))


@app.post("/export/docx")
def export_docx(request: ExportRequest) -> Response:
    payload = build_docx(
        request.tailored_cv, request.hard_covered, request.hard_total,
        request.preferred_covered, request.preferred_total, request.matched, request.missing,
    )
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="tailored-cv.docx"'},
    )


@app.post("/export/pdf")
def export_pdf(request: ExportRequest) -> Response:
    payload = build_pdf(
        request.tailored_cv, request.hard_covered, request.hard_total,
        request.preferred_covered, request.preferred_total, request.matched, request.missing,
    )
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="tailored-cv.pdf"'},
    )
