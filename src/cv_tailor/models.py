from pydantic import BaseModel, Field


class TailorRequest(BaseModel):
    job_description: str = Field(min_length=20)
    base_cv: str = Field(min_length=20)
    page_budget: int = Field(default=1, ge=1, le=2)


class QuantifiedOutcome(BaseModel):
    value: str
    unit: str                         # % | years | count | money | other
    context: str




class EvidenceRecord(BaseModel):
    """One structured unit of CV content. The guardrails and change log
    are only enforceable because units carry structure, not loose text."""
    id: str
    section: str                      # summary | experience | education | skills | other
    text: str                         # raw text, never edited
    role: str | None = None
    employer: str | None = None
    date_range: str | None = None
    skills: list[str] = []
    quantified: list[QuantifiedOutcome] = []
    verb_class: str | None = None     # build | improve | lead | deliver | analyze | support
    score: float = 0.0
    matched_terms: list[str] = []


class Requirement(BaseModel):
    id: str
    text: str
    kind: str                         # hard | preferred
    skills: list[str] = []
    min_years: int | None = None


class CoverageRow(BaseModel):
    requirement: Requirement
    status: str                       # covered | partial | missing
    evidence_ids: list[str] = []
    covered_skills: list[str] = []
    missing_skills: list[str] = []
    note: str = ""


class CoverageMatrix(BaseModel):
    rows: list[CoverageRow]
    hard_covered: int
    hard_total: int
    preferred_covered: int
    preferred_total: int


class ParseabilityCheck(BaseModel):
    id: str
    name: str
    status: str                       # pass | warn | fail
    detail: str


class TailoredUnit(BaseModel):
    id: str
    section: str
    text: str
    provenance: str                   # verbatim | rephrased | reframed
    evidence_ids: list[str] = []


class BlockedItem(BaseModel):
    text: str
    reason: str
    gate: str                         # number-allowlist | entity-allowlist | entailment


class Change(BaseModel):
    kind: str
    original: str | None = None
    replacement: str | None = None
    evidence_ids: list[str] = []
    reason: str
    provenance: str | None = None


class TailorResponse(BaseModel):
    tailored_cv: str
    tailored_units: list[TailoredUnit]
    evidence: list[EvidenceRecord]
    coverage: CoverageMatrix
    parseability: list[ParseabilityCheck]
    gaps: list[str]
    change_log: list[Change]
    blocked: list[BlockedItem]
    warnings: list[str]
    page_budget: int


class RankRequest(BaseModel):
    base_cv: str = Field(min_length=20)
    job_descriptions: list[str] = Field(min_length=1)


class RankedJob(BaseModel):
    index: int
    title: str
    hard_covered: int
    hard_total: int
    preferred_covered: int
    preferred_total: int
    coverage_ratio: float
    top_gaps: list[str]


class RankResponse(BaseModel):
    ranked: list[RankedJob]
