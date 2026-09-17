"""Post-generation verification gate.

Instructions leak, so fabrication control is a deterministic gate that
runs after generation, not a prompt:

1. Number allowlist - every number in the output must exist in the base CV.
2. Entity allowlist - every proper noun (tools, certs, employers, titles)
   in the output must exist in the base CV.
3. Entailment - every generated sentence must be entailed by its cited
   evidence: all content words come from the base CV and at least half of
   them come from the cited units themselves.

Anything that fails is blocked, not warned about: it never reaches the
preview, and the block is recorded with its reason.
"""
from __future__ import annotations

import re

from .models import BlockedItem, TailoredUnit
from .text import STANDARD_SECTIONS, STOP, tokens

NUMBER = re.compile(r"\$?\d+(?:\.\d+)?%?")
CAPITALIZED = re.compile(r"\b[A-Z][A-Za-z0-9+#.]*\b")

# Words that may legitimately appear in generated output without appearing
# as capitalized entities in the base CV (headings and common sentence
# openers).
ALLOWED_HEADINGS = {word.upper() for section in STANDARD_SECTIONS for word in section.upper().split()} | {
    "TARGETED", "SELECTED", "CV", "NAME", "CONTACT",
}


def number_allowlist(base_cv: str) -> set[str]:
    return set(NUMBER.findall(base_cv))


def entity_allowlist(base_cv: str) -> set[str]:
    return {token.lower() for token in CAPITALIZED.findall(base_cv)}


def _numbers_in(text: str) -> list[str]:
    return NUMBER.findall(text)


def _entities_in(text: str) -> list[str]:
    """Capitalized tokens, excluding sentence-openers made of common words."""
    found = []
    for match in CAPITALIZED.finditer(text):
        token = match.group()
        # First word of a sentence is capitalized by grammar, not by name;
        # only acronyms there still count as entities.
        before = text[: match.start()].rstrip()
        sentence_start = not before or before[-1] in ".!?\n:•-"
        if sentence_start:
            if token.isupper() and len(token) > 1 and token.lower() not in STOP:
                found.append(token)
        elif token.lower() not in STOP:
            found.append(token)
    return found


def check_numbers(text: str, allowed: set[str]) -> list[str]:
    return [n for n in _numbers_in(text) if n not in allowed]


def check_entities(text: str, allowed: set[str]) -> list[str]:
    bad = []
    for token in _entities_in(text):
        if token.upper() in ALLOWED_HEADINGS:
            continue
        if token.lower() not in allowed:
            bad.append(token)
    return bad


def check_entailment(sentence: str, cited_texts: list[str], base_cv: str) -> bool:
    """A sentence is entailed when its content words come from the base CV
    and at least half of them come from the evidence it cites."""
    content = set(tokens(sentence))
    if not content:
        return False
    base_tokens = set(tokens(base_cv))
    if not content <= base_tokens:
        return False
    cited_tokens = set().union(*(set(tokens(t)) for t in cited_texts)) if cited_texts else set()
    if not cited_tokens:
        return False
    overlap = len(content & cited_tokens)
    return overlap / len(content) >= 0.5


def provenance(generated: str, base_cv: str) -> str:
    """Label a generated line: verbatim, rephrased (same words, reordered
    or lightly edited), or reframed (new framing of cited evidence)."""
    norm = lambda s: re.sub(r"\s+", " ", s.strip().lower())
    if norm(generated) and norm(generated) in norm(base_cv):
        return "verbatim"
    generated_tokens = sorted(tokens(generated))
    for block in re.split(r"\n+|(?<=[.!?])\s+", base_cv):
        if sorted(tokens(block)) == generated_tokens and generated_tokens:
            return "rephrased"
    return "reframed"


def run_gate(units: list[TailoredUnit], evidence_by_id: dict[str, str], base_cv: str) -> tuple[list[TailoredUnit], list[BlockedItem]]:
    """Run all three gates. Blocked units are dropped and recorded."""
    numbers = number_allowlist(base_cv)
    entities = entity_allowlist(base_cv)
    passed: list[TailoredUnit] = []
    blocked: list[BlockedItem] = []
    for unit in units:
        bad_numbers = check_numbers(unit.text, numbers)
        if bad_numbers:
            blocked.append(BlockedItem(
                text=unit.text,
                reason=f"Numbers not present in the base CV: {', '.join(sorted(set(bad_numbers)))}",
                gate="number-allowlist",
            ))
            continue
        bad_entities = check_entities(unit.text, entities)
        if bad_entities:
            blocked.append(BlockedItem(
                text=unit.text,
                reason=f"Names not present in the base CV: {', '.join(sorted(set(bad_entities)))}",
                gate="entity-allowlist",
            ))
            continue
        cited = [evidence_by_id[eid] for eid in unit.evidence_ids if eid in evidence_by_id]
        if unit.provenance != "verbatim" and not check_entailment(unit.text, cited, base_cv):
            blocked.append(BlockedItem(
                text=unit.text,
                reason="Sentence is not entailed by its cited evidence.",
                gate="entailment",
            ))
            continue
        passed.append(unit)
    return passed, blocked
