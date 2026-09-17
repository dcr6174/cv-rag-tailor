"""Extract a job description into structured requirements.

Real applicant tracking is keyword search plus knockout filters, so the
honest unit of analysis is the requirement - hard vs preferred, with
years-per-skill - not a single percentage.
"""
from __future__ import annotations

import re

from .models import Requirement
from .text import find_skills, tokens

PREFERRED = re.compile(r"\b(preferred|preferably|nice to have|nice-to-have|bonus|a plus|ideally|desired|advantage)\b", re.IGNORECASE)
YEARS = re.compile(
    r"(\d+)\s*\+?\s*years?(?:\s+of)?\s+(?:[a-z]+\s){0,2}?(?:experience\s+)?(?:in|with|of\s+)?([A-Za-z][A-Za-z0-9+#/. -]{0,40})",
    re.IGNORECASE,
)

_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def parse_requirements(jd: str) -> list[Requirement]:
    """One requirement per JD sentence or bullet, classified hard/preferred."""
    requirements: list[Requirement] = []
    counter = 0
    for chunk in _SPLIT.split(jd):
        text = chunk.strip().lstrip("-•*· ").strip()
        if len(text) < 4:
            continue
        skills = find_skills(text)
        if not skills and len(tokens(text)) < 2:
            continue
        counter += 1
        min_years = None
        year_match = YEARS.search(text)
        if year_match:
            min_years = int(year_match.group(1))
            skill_span = year_match.group(2).strip()
            for skill in find_skills(skill_span):
                if skill not in skills:
                    skills.append(skill)
        requirements.append(
            Requirement(
                id=f"req-{counter}",
                text=text,
                kind="preferred" if PREFERRED.search(text) else "hard",
                skills=sorted(set(skills)),
                min_years=min_years,
            )
        )
    return requirements
