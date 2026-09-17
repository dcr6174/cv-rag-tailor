# Grounded CV RAG Tailor

A portfolio-grade JD-to-CV tailoring service that treats the base CV as the only source of truth. It retrieves CV evidence relevant to a job description, reports ATS-style matches and gaps, and produces a targeted CV without claiming skills or results that are not in the source.

## Why this is RAG

The job description is the query. The base CV is split into evidence chunks, normalized, and ranked by term overlap. Only retrieved chunks may feed the targeted summary. Every change carries evidence IDs so a reviewer can trace it back to the CV.

## Output

`POST /tailor` returns:

- `tailored_cv`: original CV plus a grounded targeted summary
- `match_report`: 0-100 keyword coverage, matched terms, missing terms, and evidence coverage
- `evidence`: ranked source chunks with stable IDs and matched terms
- `gaps`: JD terms absent from the CV
- `change_log`: each edit, rationale, and supporting evidence IDs
- `warnings`: missing-skill and unsupported-number checks

The tool deliberately does not add a missing skill. A candidate can use the gap report to decide what to learn or whether other genuine experience belongs in the base CV.

## Architecture

```text
JD -> normalization/keywords ----\
                                  -> evidence retriever -> grounded summary
Base CV -> chunking/tokenization -/                         |
            |                                               v
            +-----------------> ATS report + gaps -> response + change log
                                                        |
                                                        v
                                                fabrication guards
```

The implementation is deterministic and runs locally. No API key, hosted LLM, candidate data upload, or external service is required. This makes tests repeatable and keeps personal data on the machine. A production extension can place a schema-constrained LLM behind the same evidence contract, then reject output whose claims lack evidence IDs.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn cv_tailor.api:app --reload
```

Open `http://127.0.0.1:8000/docs`, call `/tailor`, and paste a JD and plain-text CV.

Example with curl:

```bash
curl -s http://127.0.0.1:8000/tailor \
  -H 'content-type: application/json' \
  -d "$(python - <<'PY'
import json
print(json.dumps({
  'job_description': open('samples/job_description.txt').read(),
  'base_cv': open('samples/base_cv.txt').read()
}))
PY
)"
```

## Test

```bash
pip install -e '.[dev]'
pytest -q
```

The suite covers normalization, chunking, retrieval, stable evidence IDs, ATS scoring, missing-skill handling, change provenance, source preservation, and quantified-claim checks.

## Safety and privacy

- The base CV is the sole experience source.
- Missing terms remain gaps and are never silently inserted.
- New numeric claims are flagged.
- No sample contains private contact details.
- `.env`, PDFs, DOCX files, and generated output are ignored.
- No credentials or secrets are needed or stored.

This is an ATS-style heuristic, not an official score from an employer's ATS. Keyword coverage is useful for review but does not predict hiring outcomes.

## Production roadmap

- PDF/DOCX parsing with layout-aware export
- BM25 plus embedding-based hybrid retrieval
- user approval of each suggested change
- schema-constrained LLM rewriting with sentence-level evidence validation
- encrypted storage, deletion controls, and audit events
- evaluation set measuring evidence precision and unsupported-claim rate

## Truthful portfolio bullets

- Built a local JD-to-CV RAG service in Python and FastAPI that retrieves relevant CV evidence and generates a targeted, source-grounded summary.
- Added an ATS-style keyword report, explicit skill-gap output, and an evidence-linked change log so every suggested edit is reviewable.
- Implemented fabrication guards that keep missing skills out of the tailored CV and flag new quantified claims.
- Wrote 18 automated tests covering text normalization, retrieval, scoring, provenance, gap handling, and end-to-end tailoring.

## Interview talking points

- **Why deterministic retrieval?** It gives a repeatable offline baseline and makes unsupported claims easy to inspect before adding an LLM.
- **How is hallucination reduced?** Generation can only use retrieved base-CV chunks; missing JD terms go to `gaps`; edits cite evidence IDs; numeric claims are checked against the source.
- **What would you change at scale?** Use layout-aware ingestion, hybrid search, a vector database, constrained generation, encrypted tenant storage, and offline evaluation for evidence precision and claim support.
- **What does the score mean?** It is transparent JD keyword coverage, not a claim to reproduce a proprietary ATS.

## License

MIT
