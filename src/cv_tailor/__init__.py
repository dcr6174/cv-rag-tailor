"""cv-rag-tailor: evidence-grounded CV tailoring with a verification gate."""
from .pipeline import rank_jobs, tailor_cv

__all__ = ["tailor_cv", "rank_jobs"]
__version__ = "0.3.0"
