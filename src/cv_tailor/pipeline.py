"""The v0.3 tailoring pipeline.

Parse the CV into structured evidence records, parse the JD into
structured requirements, score every unit, compose a tailored CV inside a
page budget, then pass every generated line through the verification
gate. Only lines that prove they belong survive.
"""
from __future__ import annotations

import re

from .evidence import parse_evidence
from .models import (
    Change,
    CoverageMatrix,
    CoverageRow,
    RankedJob,
    TailoredUnit,
    TailorResponse,
)
from .parseability import check_parseability
from .requirements import parse_requirements
from .retrieval import score_evidence
from .text import find_skills
from .verify import provenance, run_gate

LINES_PER_PAGE = 48
WRAP = 95


def _line_cost(text: str) -> int:
    return max(1, len(text) // WRAP + 1)


def build_coverage(requirements, scored_units) -> CoverageMatrix:
    """Match each requirement against the scored evidence records."""
    rows: list[CoverageRow] = []
    for req in requirements:
        hits = [
            unit for unit in scored_units
            if set(req.skills) & set(unit.skills)
        ]
        covered_skills = set().union(*(set(u.skills) & set(req.skills) for u in hits)) if hits else set()
        if req.skills and covered_skills >= set(req.skills):
            status = "covered"
        elif covered_skills or (not req.skills and hits):
            status = "partial"
        else:
            status = "missing"
        note = ""
        if req.min_years and status != "missing":
            note = f"JD asks for {req.min_years}+ years; confirm your timeline supports it."
        missing_skills = sorted(set(req.skills) - covered_skills)
        rows.append(CoverageRow(
            requirement=req,
            status=status,
            evidence_ids=[u.id for u in hits[:4]],
            note=note,
            covered_skills=sorted(covered_skills),
            missing_skills=missing_skills,
        ))
    hard = [r for r in rows if r.requirement.kind == "hard"]
    pref = [r for r in rows if r.requirement.kind == "preferred"]
    return CoverageMatrix(
        rows=rows,
        hard_covered=sum(1 for r in hard if r.status == "covered"),
        hard_total=len(hard),
        preferred_covered=sum(1 for r in pref if r.status == "covered"),
        preferred_total=len(pref),
    )


def _verb_led(clause: str) -> bool:
    """True when a clause opens with a verb, so swapping clauses stays
    grammatical: 'Tested X and added Y' -> 'Added Y and tested X'."""
    first = re.findall(r"[a-zA-Z]+", clause)
    if not first:
        return False
    word = first[0].lower()
    if word.endswith(("ed", "ing")):
        return True
    from .evidence import VERB_CLASSES
    return any(word in verbs for verbs in VERB_CLASSES.values())


def _reorder_for_impact(text: str, jd_terms: set[str]) -> str | None:
    """Move the JD-relevant clause first when the sentence splits cleanly
    into two verb-led clauses. Same words, new order - which is exactly
    what 'rephrased' means. Returns None when there is no clean split.
    """
    for sep in (" and ", ", "):
        if sep not in text:
            continue
        left, right = text.split(sep, 1)
        left, right = left.strip(), right.strip()
        if len(left) < 12 or len(right) < 12:
            continue
        if not (_verb_led(left) and _verb_led(right)):
            continue
        left_overlap = len(set(re.findall(r"[a-z]+", left.lower())) & jd_terms)
        right_overlap = len(set(re.findall(r"[a-z]+", right.lower())) & jd_terms)
        if right_overlap > left_overlap and right_overlap > 0:
            joined = right[0].upper() + right[1:] + sep + left[0].lower() + left[1:]
            if not joined.endswith("."):
                joined += "."
            return joined
    return None


def tailor_cv(base_cv: str, job_description: str, page_budget: int = 1) -> TailorResponse:
    units_all = parse_evidence(base_cv)
    requirements = parse_requirements(job_description)
    scored = score_evidence(units_all, job_description)
    coverage = build_coverage(requirements, scored)
    evidence_by_id = {u.id: u.text for u in units_all}
    jd_terms = set(re.findall(r"[a-z]+", job_description.lower()))

    tailored_units: list[TailoredUnit] = []
    changes: list[Change] = []
    budget = LINES_PER_PAGE * page_budget
    used = 0

    def spend(unit: TailoredUnit) -> bool:
        nonlocal used
        cost = _line_cost(unit.text)
        if used + cost > budget:
            return False
        tailored_units.append(unit)
        used += cost
        return True

    # Header: name and contact lines, always kept.
    for unit in units_all:
        if unit.section == "header":
            spend(TailoredUnit(id="t-header-" + unit.id, section="header", text=unit.text,
                               provenance="verbatim", evidence_ids=[unit.id]))

    # Targeted summary: reframed from the top evidence, cited per sentence.
    top = [u for u in scored if u.section in {"experience", "summary", "projects"}][:4]
    if top:
        sentences = sorted(
            (s.strip() for u in top[:3] for s in re.split(r"(?<=[.!?])\s+|\n+", u.text) if len(s.strip()) > 20),
            key=lambda s: -len(set(re.findall(r"[a-z]+", s.lower())) & jd_terms),
        )[:2]
        if sentences:
            summary_text = " ".join(s if s.endswith((".", "!", "?")) else s + "." for s in sentences)
            summary = TailoredUnit(
                id="t-summary", section="summary", text=summary_text,
                provenance=provenance(summary_text, base_cv),
                evidence_ids=[u.id for u in top[:3]],
            )
            if spend(summary):
                changes.append(Change(
                    kind="add", replacement=summary_text,
                    evidence_ids=summary.evidence_ids,
                    reason="Surfaces JD-relevant experience already present in the base CV.",
                    provenance=summary.provenance,
                ))

    # Body: best evidence first, inside the page budget. Quantified,
    # JD-relevant bullets get a clean impact-first reorder when possible.
    body = [u for u in scored if u.section in {"experience", "projects", "summary"} and u.score > 0]
    body += [u for u in units_all if u.section in {"experience", "projects"} and u.score <= 0]
    summary_norm = re.sub(r"\s+", " ", tailored_units[-1].text.lower()) if tailored_units and tailored_units[-1].id == "t-summary" else ""
    seen: set[str] = set()
    for unit in body:
        if unit.text in seen:
            continue
        seen.add(unit.text)
        if summary_norm and re.sub(r"\s+", " ", unit.text.lower()).rstrip(".") in summary_norm:
            continue  # already surfaced in the targeted summary
        text = unit.text
        prov = "verbatim"
        reordered = _reorder_for_impact(unit.text, jd_terms)
        if reordered and reordered != unit.text:
            text = reordered
            prov = "rephrased"
        t_unit = TailoredUnit(id="t-" + unit.id, section=unit.section, text=text,
                              provenance=prov, evidence_ids=[unit.id])
        if spend(t_unit):
            if prov == "rephrased":
                changes.append(Change(
                    kind="rephrase", original=unit.text, replacement=text,
                    evidence_ids=[unit.id],
                    reason="Moved the JD-relevant clause first; no words added or removed.",
                    provenance="rephrased",
                ))
        else:
            changes.append(Change(
                kind="omit", original=unit.text, evidence_ids=[unit.id],
                reason=f"Strong match, but it does not fit the {page_budget}-page budget.",
            ))

    # Verification gate: blocked lines never reach the preview.
    passed, blocked = run_gate(tailored_units, evidence_by_id, base_cv)

    tailored_cv = _render(passed)
    gaps = sorted({skill for row in coverage.rows for skill in row.missing_skills})
    warnings: list[str] = []
    if gaps:
        warnings.append("Missing JD requirements are reported as gaps, not inserted as claimed experience.")
    if blocked:
        warnings.append(f"{len(blocked)} generated line(s) were blocked by the verification gate and removed.")

    return TailorResponse(
        tailored_cv=tailored_cv,
        tailored_units=passed,
        evidence=scored,
        coverage=coverage,
        parseability=check_parseability(base_cv),
        gaps=gaps,
        change_log=changes,
        blocked=blocked,
        warnings=warnings,
        page_budget=page_budget,
    )


def _render(units: list[TailoredUnit]) -> str:
    section_titles = {"header": "", "summary": "TARGETED SUMMARY", "experience": "EXPERIENCE",
                      "projects": "PROJECTS", "skills": "SKILLS", "education": "EDUCATION", "other": "OTHER"}
    out: list[str] = []
    current = None
    for unit in units:
        if unit.section != current:
            current = unit.section
            title = section_titles.get(current, current.upper())
            if title:
                out.append("\n" + title if out else title)
        out.append(unit.text)
    return "\n".join(out).strip()


def rank_jobs(base_cv: str, job_descriptions: list[str]) -> list[RankedJob]:
    """Score and rank several JDs against one CV - which roles fit best?"""
    units_all = parse_evidence(base_cv)
    ranked: list[RankedJob] = []
    for index, jd in enumerate(job_descriptions):
        requirements = parse_requirements(jd)
        scored = score_evidence(units_all, jd)
        coverage = build_coverage(requirements, scored)
        hard_rows = [r for r in coverage.rows if r.requirement.kind == "hard"]
        pref_rows = [r for r in coverage.rows if r.requirement.kind == "preferred"]
        ratio = (sum(_row_fraction(r) for r in hard_rows) + 0.5 * sum(_row_fraction(r) for r in pref_rows)) / max(len(hard_rows), 1)
        first_line = next((line.strip() for line in jd.splitlines() if len(line.strip()) > 3), "Job description")
        gaps = sorted({s for row in coverage.rows for s in row.missing_skills})
        ranked.append(RankedJob(
            index=index,
            title=first_line[:70],
            hard_covered=coverage.hard_covered,
            hard_total=coverage.hard_total,
            preferred_covered=coverage.preferred_covered,
            preferred_total=coverage.preferred_total,
            coverage_ratio=round(ratio, 3),
            top_gaps=gaps[:4],
        ))
    return sorted(ranked, key=lambda r: (-r.coverage_ratio, r.index))


def _row_fraction(row) -> float:
    """How much of one requirement is covered: fraction of its skills,
    or the coarse status when the requirement names no lexicon skills."""
    total = len(row.requirement.skills)
    if total:
        return len(row.covered_skills) / total
    return {"covered": 1.0, "partial": 0.5, "missing": 0.0}[row.status]
