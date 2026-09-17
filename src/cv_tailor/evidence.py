"""Parse CV text into structured evidence records.

A CV is 50-200 evidence units, not loose chunks. Structure - role,
employer, dates, skills, quantified outcomes, verb class - is what makes
the verification gate and the change log enforceable.
"""
from __future__ import annotations

import re

from .models import EvidenceRecord, QuantifiedOutcome
from .text import STANDARD_SECTIONS, find_skills, tokens

MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
DATE_RANGE = re.compile(
    rf"(?P<range>(?:({MONTHS})\w*\.?\s*)?\d{{4}}\s*(?:[-–—]|to)\s*(?:(?:({MONTHS})\w*\.?\s*)?\d{{4}}|present|current|now))",
    re.IGNORECASE,
)
QUANT = re.compile(
    r"(?P<value>\$\s?\d[\d,]*(?:\.\d+)?[kKmM]?|\d+(?:\.\d+)?\s?(?:%|percent|x\b|k\b|K\b|years?|yrs?|hrs?|hours?|minutes?|users?|engineers?|people|teams?|clients?|projects?|releases?))"
)
HEADING = re.compile(r"^[A-Z][A-Z &/()-]{1,48}$")

VERB_CLASSES = {
    "build": {"built", "build", "created", "create", "developed", "develop", "designed", "design", "implemented", "implement", "launched", "launch", "wrote", "write", "authored", "engineered", "architected", "automated", "automate"},
    "improve": {"reduced", "reduce", "improved", "improve", "increased", "increase", "optimized", "optimize", "accelerated", "cut", "raised", "grew", "streamlined", "saved"},
    "lead": {"led", "lead", "managed", "manage", "mentored", "mentor", "coached", "owned", "own", "directed", "headed", "supervised"},
    "deliver": {"delivered", "deliver", "shipped", "ship", "released", "deployed", "deploy", "migrated", "rolled"},
    "analyze": {"analyzed", "analyze", "tested", "test", "measured", "evaluated", "assessed", "audited", "reviewed", "investigated"},
    "support": {"supported", "support", "maintained", "maintain", "collaborated", "partnered", "assisted", "helped", "added", "add"},
}


def _is_heading(line: str) -> bool:
    clean = line.strip().rstrip(":")
    if not clean or len(clean) > 50:
        return False
    if clean.lower() in STANDARD_SECTIONS:
        return True
    return bool(HEADING.match(clean)) and clean.lower() not in {"dear", "to whom it may concern"}


def _section_key(heading: str) -> str:
    return STANDARD_SECTIONS.get(heading.strip().rstrip(":").lower(), "other")


def _verb_class(line: str) -> str | None:
    words = re.findall(r"[a-zA-Z]+", line.lower())
    for word in words[:3]:
        for klass, verbs in VERB_CLASSES.items():
            if word in verbs:
                return klass
    return None


def _quantified(line: str) -> list[QuantifiedOutcome]:
    found = []
    for match in QUANT.finditer(line):
        raw = match.group("value").strip()
        unit = "other"
        low = raw.lower()
        if "%" in low or "percent" in low:
            unit = "%"
        elif "year" in low or "yr" in low:
            unit = "years"
        elif low.startswith("$"):
            unit = "money"
        elif re.search(r"\d\s?(x|k)\b", low):
            unit = "count"
        found.append(QuantifiedOutcome(value=raw, unit=unit, context=line.strip()))
    return found


def _role_employer(line: str) -> tuple[str | None, str | None]:
    """Heuristic role/employer split for experience heading lines."""
    text = DATE_RANGE.sub("", line).strip(" -–—|,")
    for sep in (" at ", " @ ", " | ", " — ", " – ", " - "):
        if sep in text:
            left, right = (p.strip() for p in text.split(sep, 1))
            if left and right:
                return left, right
    if ", " in text:
        left, right = (p.strip() for p in text.rsplit(", ", 1))
        if left and right and len(right.split()) <= 6:
            return left, right
    return (text or None), None


def parse_evidence(cv: str) -> list[EvidenceRecord]:
    """Split CV text into structured, stably-id'd evidence records."""
    records: list[EvidenceRecord] = []
    section = "header"
    counter = 0

    def add(text: str, sec: str) -> None:
        nonlocal counter
        counter += 1
        role, employer = (None, None)
        date = None
        if sec == "experience":
            match = DATE_RANGE.search(text)
            if match:
                date = match.group("range").strip()
            if len(text) < 120 and (" at " in text or " | " in text or ", " in text or DATE_RANGE.search(text)):
                role, employer = _role_employer(text)
        records.append(
            EvidenceRecord(
                id=f"ev-{counter}",
                section=sec,
                text=text.strip(),
                role=role,
                employer=employer,
                date_range=date,
                skills=find_skills(text),
                quantified=_quantified(text),
                verb_class=_verb_class(text),
            )
        )

    first_line = True
    for raw in cv.splitlines():
        line = raw.strip()
        if not line:
            continue
        if first_line:
            # The opening line is the candidate's name, never a heading.
            first_line = False
            add(line, "header")
            continue
        if _is_heading(line):
            section = _section_key(line)
            continue
        add(line.lstrip("-•*· ").strip(), section)

    return records


def content_tokens(text: str) -> set[str]:
    return set(tokens(text))
