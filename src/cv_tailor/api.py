from fastapi import FastAPI
from .models import TailorRequest, TailorResponse
from .pipeline import tailor_cv

app = FastAPI(title="Grounded CV RAG Tailor", version="0.1.0")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/tailor", response_model=TailorResponse)
def tailor(request: TailorRequest) -> TailorResponse:
    return tailor_cv(request.base_cv, request.job_description)
