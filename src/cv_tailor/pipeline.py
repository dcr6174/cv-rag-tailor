from .guardrails import grounded_summary, unsupported_claims
from .models import TailorResponse, MatchReport, Change
from .retrieval import retrieve
from .text import keywords, tokens

def tailor_cv(base_cv: str, job_description: str) -> TailorResponse:
    evidence = retrieve(base_cv, job_description)
    jd_keywords = keywords(job_description)
    cv_terms = set(tokens(base_cv))
    matched = [k for k in jd_keywords if k in cv_terms]
    missing = [k for k in jd_keywords if k not in cv_terms]
    score = round(100 * len(matched) / max(len(jd_keywords), 1))
    coverage = round(len({term for item in evidence for term in item.matched_terms}) / max(len(set(jd_keywords)), 1), 3)

    summary = grounded_summary("\n".join(e.text for e in evidence[:4]), job_description)
    tailored = base_cv.strip()
    changes: list[Change] = []
    if summary:
        targeted = "TARGETED SUMMARY\n" + summary
        tailored = targeted + "\n\n" + tailored
        changes.append(Change(kind="add", replacement=targeted, evidence_ids=[e.id for e in evidence[:4]], reason="Surfaces JD-relevant experience already present in the base CV."))

    warnings = unsupported_claims(tailored, base_cv)
    if missing:
        warnings.append("Missing JD terms are reported as gaps, not inserted as claimed experience.")
    return TailorResponse(
        tailored_cv=tailored,
        match_report=MatchReport(score=score, matched_keywords=matched, missing_keywords=missing, evidence_coverage=coverage),
        evidence=evidence,
        gaps=missing,
        change_log=changes,
        warnings=warnings,
    )
