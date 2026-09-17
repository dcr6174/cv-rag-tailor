import re
from .text import tokens

NUMBER = re.compile(r"\b\d+(?:\.\d+)?%?\b")

def unsupported_claims(tailored: str, base_cv: str) -> list[str]:
    base_numbers = set(NUMBER.findall(base_cv))
    new_numbers = sorted(set(NUMBER.findall(tailored)) - base_numbers)
    return [f"New quantified claim not found in the base CV: {n}" for n in new_numbers]

def grounded_summary(evidence_text: str, jd: str) -> str:
    jd_terms = set(tokens(jd))
    sentences = re.split(r"(?<=[.!?])\s+|\n+", evidence_text)
    ranked = sorted((s.strip() for s in sentences if s.strip()), key=lambda s: -len(set(tokens(s)) & jd_terms))
    return " ".join(ranked[:2])
