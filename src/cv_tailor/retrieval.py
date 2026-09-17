import math
from .models import Evidence
from .text import tokens, sections

def retrieve(cv: str, jd: str, top_k: int = 8) -> list[Evidence]:
    query = set(tokens(jd))
    scored = []
    for i, chunk in enumerate(sections(cv), 1):
        words = set(tokens(chunk))
        overlap = sorted(query & words)
        if not overlap:
            continue
        precision = len(overlap) / max(len(words), 1)
        recall = len(overlap) / max(len(query), 1)
        score = (2 * precision * recall / max(precision + recall, 1e-9)) * (1 + math.log1p(len(overlap)))
        scored.append(Evidence(id=f"cv-{i}", text=chunk, score=round(score, 4), matched_terms=overlap))
    return sorted(scored, key=lambda e: (-e.score, e.id))[:top_k]
