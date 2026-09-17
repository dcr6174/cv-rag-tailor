"""Score every evidence unit on every request.

A CV is 50-200 evidence units - far too small for approximate nearest
neighbour search. BM25 over all units, then a deterministic rerank that
rewards exact skill hits, is cheaper and more accurate at this scale.
"""
from __future__ import annotations

import math
from collections import Counter

from .models import EvidenceRecord
from .text import find_skills, tokens

K1 = 1.5
B = 0.75


def bm25_scores(query_terms: list[str], units: list[EvidenceRecord]) -> dict[str, float]:
    docs = {unit.id: tokens(unit.text) for unit in units}
    if not docs:
        return {}
    avg_len = sum(len(d) for d in docs.values()) / len(docs)
    doc_freq: Counter[str] = Counter()
    for doc in docs.values():
        for term in set(doc):
            doc_freq[term] += 1
    n_docs = len(docs)
    scores: dict[str, float] = {}
    for unit_id, doc in docs.items():
        counts = Counter(doc)
        score = 0.0
        for term in query_terms:
            tf = counts.get(term, 0)
            if not tf:
                continue
            idf = math.log(1 + (n_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            denom = tf + K1 * (1 - B + B * len(doc) / max(avg_len, 1e-9))
            score += idf * (tf * (K1 + 1)) / denom
        scores[unit_id] = score
    return scores


def score_evidence(units: list[EvidenceRecord], jd: str) -> list[EvidenceRecord]:
    """Attach BM25 + exact-skill rerank scores to every unit, best first."""
    query = tokens(jd)
    jd_skills = set(find_skills(jd))
    base = bm25_scores(query, units)
    scored: list[EvidenceRecord] = []
    for unit in units:
        overlap = sorted(set(tokens(unit.text)) & set(query))
        exact = jd_skills & set(unit.skills)
        # Rerank: BM25 plus a deterministic boost per exact skill hit.
        final = base.get(unit.id, 0.0) + 1.5 * math.log1p(len(exact))
        if final <= 0:
            continue
        unit.score = round(final, 4)
        unit.matched_terms = overlap
        scored.append(unit)
    return sorted(scored, key=lambda u: (-u.score, u.id))
