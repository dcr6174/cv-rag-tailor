import re
from collections import Counter

STOP = {"and","the","with","for","that","from","this","you","your","our","are","will","have","has","into","using","job","role","work","years","skills","required","preferred","need","own","skilled","quality","a","an","to","of","in","on","is","be","as","or","we","at","it","by"}
TOKEN = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}")

ALIASES = {"quality assurance":"qa", "continuous integration":"ci", "continuous delivery":"cd", "application programming interface":"api"}

def normalize(text: str) -> str:
    value = text.lower()
    for phrase, alias in ALIASES.items():
        value = value.replace(phrase, alias)
    return value

def tokens(text: str) -> list[str]:
    return [t.strip(".-").lower() for t in TOKEN.findall(normalize(text)) if t.lower() not in STOP and len(t.strip(".-")) > 1]

def keywords(text: str, limit: int = 30) -> list[str]:
    counts = Counter(tokens(text))
    return [word for word, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:limit]]

def sections(cv: str) -> list[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", cv) if b.strip()]
    result = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        result.extend(lines if len(block) > 500 else [block])
    return result
