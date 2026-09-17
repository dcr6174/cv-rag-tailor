import re
from collections import Counter

STOP = {"and","the","with","for","that","from","this","you","your","our","are","will","have","has","into","using","job","role","work","years","year","skills","required","preferred","need","own","skilled","quality","a","an","to","of","in","on","is","be","as","or","we","at","it","by","who","what","their","they","them","team","teams","ability","strong","experience","experienced","including","such","etc","plus","must","should","can","all","any","each","other","more","most","new","over","under","per","via","within","across","about","also","etc"}
TOKEN = re.compile(r"[a-zA-Z][a-zA-Z0-9+#./-]{1,}")

ALIASES = {"quality assurance":"qa", "continuous integration":"ci", "continuous delivery":"cd", "application programming interface":"api"}

# A small local skills lexicon. Matching is case-insensitive; multi-word
# entries are matched on the normalized text before tokenization.
SKILL_LEXICON = [
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#", "ruby", "php", "swift", "kotlin", "scala", "sql",
    "selenium", "playwright", "cypress", "appium", "postman", "rest api", "rest", "api", "graphql", "grpc",
    "ci/cd", "ci", "cd", "jenkins", "github actions", "gitlab", "circleci", "travis",
    "docker", "kubernetes", "terraform", "ansible", "aws", "azure", "gcp", "linux",
    "react", "angular", "vue", "node", "django", "flask", "fastapi", "spring", "rails",
    "test automation", "performance testing", "load testing", "unit testing", "integration testing",
    "regression", "qa", "testing", "automation", "debugging", "monitoring", "observability",
    "git", "jira", "confluence", "agile", "scrum", "kanban",
    "machine learning", "ml", "ai", "data analysis", "pandas", "numpy", "pytorch", "tensorflow",
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "kafka", "rabbitmq",
    "microservices", "distributed systems", "system design", "security", "oauth", "saml",
    "excel", "powerpoint", "tableau", "power bi", "looker",
    "project management", "stakeholder management", "mentoring", "hiring",
]

STANDARD_SECTIONS = {
    "summary": "summary", "professional summary": "summary", "profile": "summary", "objective": "summary",
    "experience": "experience", "work experience": "experience", "employment": "experience",
    "professional experience": "experience", "work history": "experience",
    "education": "education", "skills": "skills", "technical skills": "skills",
    "projects": "projects", "certifications": "certifications", "certificates": "certifications",
    "awards": "awards", "publications": "publications", "languages": "languages",
}

def normalize(text: str) -> str:
    value = text.lower()
    for phrase, alias in ALIASES.items():
        value = value.replace(phrase, alias)
    return value

def tokens(text: str) -> list[str]:
    return [t.strip(".-/").lower() for t in TOKEN.findall(normalize(text)) if t.lower() not in STOP and len(t.strip(".-/")) > 1]

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

def find_skills(text: str) -> list[str]:
    """Return lexicon skills present in the text (longest match first, deduped)."""
    norm = normalize(text)
    found = []
    for skill in sorted(SKILL_LEXICON, key=len, reverse=True):
        # Tolerate a simple plural on skills longer than two letters.
        stem = re.escape(skill) + ("s?" if len(skill) > 2 and skill[-1].isalpha() else "")
        pattern = r"(?<![a-z0-9+#/])" + stem + r"(?![a-z0-9])"
        if re.search(pattern, norm) and skill not in found:
            # Avoid double counting skills contained in longer matches
            if not any(
                skill != other
                and re.search(r"(^|[/ ])" + re.escape(skill) + r"($|[/ ])", other)
                for other in found
            ):
                found.append(skill)
    return sorted(found)
