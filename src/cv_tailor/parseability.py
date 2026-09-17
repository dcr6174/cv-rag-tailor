"""ATS parseability checks.

Real applicant tracking systems don't hand candidates a score. What they
actually do is parse the file into fields and run keyword searches. These
checks answer the honest question: will this CV survive parsing?
"""
from __future__ import annotations

import re

from .evidence import DATE_RANGE
from .models import ParseabilityCheck
from .text import STANDARD_SECTIONS

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"(?:\+?\d[\d ()-]{7,}\d)")
TABLE_CHARS = re.compile(r"\|{1,}| {3,}\S+ {3,}\S+")


def check_parseability(cv: str) -> list[ParseabilityCheck]:
    checks: list[ParseabilityCheck] = []
    lines = [line for line in cv.splitlines() if line.strip()]

    table_lines = [line for line in lines if "|" in line or "\t" in line]
    checks.append(ParseabilityCheck(
        id="layout",
        name="Single-column layout",
        status="fail" if table_lines else "pass",
        detail=(
            f"{len(table_lines)} line(s) use table or column characters; parsers often scramble these."
            if table_lines else
            "No tables, tabs, or multi-column markers detected."
        ),
    ))

    headings = []
    for line in lines:
        clean = line.strip().rstrip(":")
        if clean and len(clean) <= 50 and (clean.isupper() or clean.lower() in STANDARD_SECTIONS):
            headings.append(clean)
    nonstandard = [h for h in headings if h.lower() not in STANDARD_SECTIONS and h != lines[0].strip()]
    if not headings:
        checks.append(ParseabilityCheck(
            id="sections", name="Standard section names", status="warn",
            detail="No recognizable section headings. Parsers look for Summary, Experience, Education, Skills.",
        ))
    elif nonstandard:
        checks.append(ParseabilityCheck(
            id="sections", name="Standard section names", status="warn",
            detail="Non-standard headings: " + ", ".join(nonstandard[:5]),
        ))
    else:
        checks.append(ParseabilityCheck(
            id="sections", name="Standard section names", status="pass",
            detail="All headings use standard names parsers recognize.",
        ))

    has_email = bool(EMAIL.search(cv))
    has_phone = bool(PHONE.search(cv))
    checks.append(ParseabilityCheck(
        id="contact",
        name="Machine-readable contact details",
        status="pass" if (has_email and has_phone) else "warn",
        detail=(
            "Email and phone detected."
            if (has_email and has_phone) else
            "Missing " + ("email" if not has_email else "phone") + "; parsers need plain-text contact details."
        ),
    ))

    graphics_hint = any(marker in cv.lower() for marker in ("[image]", "[photo]", "[logo]", "<img"))
    checks.append(ParseabilityCheck(
        id="graphics",
        name="No text trapped in graphics",
        status="warn" if graphics_hint else "pass",
        detail=(
            "Image markers found; text inside images is invisible to parsers."
            if graphics_hint else
            "Plain text throughout; nothing trapped in images or icons."
        ),
    ))

    date_lines = [line for line in lines if DATE_RANGE.search(line)]
    checks.append(ParseabilityCheck(
        id="dates",
        name="Parseable date ranges",
        status="pass" if date_lines else "warn",
        detail=(
            f"{len(date_lines)} line(s) use clear date ranges."
            if date_lines else
            "No date ranges like '2021 - 2023' found; roles without dates parse poorly."
        ),
    ))

    estimated_pages = max(1, round(sum(max(1, len(line) // 95 + 1) for line in lines) / 48))
    checks.append(ParseabilityCheck(
        id="length",
        name="Length within two pages",
        status="pass" if estimated_pages <= 2 else "warn",
        detail=f"Estimated at about {estimated_pages} page(s) of plain text.",
    ))
    return checks
