from pydantic import BaseModel, Field

class TailorRequest(BaseModel):
    job_description: str = Field(min_length=20)
    base_cv: str = Field(min_length=20)

class Evidence(BaseModel):
    id: str
    text: str
    score: float
    matched_terms: list[str]

class MatchReport(BaseModel):
    score: int
    matched_keywords: list[str]
    missing_keywords: list[str]
    evidence_coverage: float

class Change(BaseModel):
    kind: str
    original: str | None = None
    replacement: str | None = None
    evidence_ids: list[str] = []
    reason: str

class TailorResponse(BaseModel):
    tailored_cv: str
    match_report: MatchReport
    evidence: list[Evidence]
    gaps: list[str]
    change_log: list[Change]
    warnings: list[str]
