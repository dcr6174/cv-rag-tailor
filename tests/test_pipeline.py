from cv_tailor.evidence import parse_evidence
from cv_tailor.models import TailoredUnit
from cv_tailor.parseability import check_parseability
from cv_tailor.pipeline import rank_jobs, tailor_cv
from cv_tailor.requirements import parse_requirements
from cv_tailor.retrieval import score_evidence
from cv_tailor.text import find_skills, keywords, tokens
from cv_tailor.verify import (
    check_entities,
    check_numbers,
    entity_allowlist,
    number_allowlist,
    provenance,
    run_gate,
)

CV = """CHANDRA QA ENGINEER
chandra@example.com +91 98765 43210

SUMMARY
QA engineer experienced in API testing and test automation.

EXPERIENCE
QA Engineer at TestLabs, 2020 - 2023
Built Selenium and Python regression tests for web applications.
Reduced regression time by 30%.
Tested REST APIs with Postman and added tests to CI pipelines.

EDUCATION
B.Tech in Computer Science, 2016 - 2020
"""
JD = """We need a QA automation engineer skilled in Python, Selenium, REST API testing, CI/CD, Playwright, and performance testing. The engineer will own regression quality."""

EXTRA = "\n".join(f"Built automation suite {i} for client projects." for i in range(1, 90))
BIG_CV = CV.replace("\n\nEDUCATION", "\n" + EXTRA + "\n\nEDUCATION")


# --- text ---
def test_tokenize_normalizes_case(): assert "python" in tokens("PYTHON")
def test_keywords_drop_stopwords(): assert "the" not in keywords("the Python engineer")
def test_find_skills_handles_plurals(): assert "rest api" in find_skills("Tested REST APIs daily")
def test_find_skills_no_double_count(): assert "ci" not in find_skills("CI/CD pipelines") and "ci/cd" in find_skills("CI/CD pipelines")

# --- structured evidence ---
def test_evidence_ids_are_stable(): assert parse_evidence(CV)[0].id == "ev-1"
def test_evidence_sections(): assert any(r.section == "experience" for r in parse_evidence(CV))
def test_evidence_role_employer_dates():
    rec = next(r for r in parse_evidence(CV) if r.role)
    assert rec.employer and "TestLabs" in rec.employer
    assert rec.date_range and "2020" in rec.date_range
def test_evidence_quantified_outcome():
    rec = next(r for r in parse_evidence(CV) if "30%" in r.text)
    assert rec.quantified[0].unit == "%"
def test_evidence_verb_class():
    rec = next(r for r in parse_evidence(CV) if r.text.startswith("Reduced"))
    assert rec.verb_class == "improve"
def test_evidence_skills_structured():
    rec = next(r for r in parse_evidence(CV) if r.text.startswith("Built"))
    assert {"python", "selenium"} <= set(rec.skills)

# --- requirements ---
def test_requirement_kinds():
    reqs = parse_requirements(JD + "\nKubernetes would be a plus.")
    assert any(r.kind == "preferred" for r in reqs if "plus" in r.text)
    assert all(r.kind == "hard" for r in reqs if "plus" not in r.text)
def test_requirement_min_years():
    reqs = parse_requirements("Must have 5+ years of Python experience.")
    assert reqs[0].min_years == 5 and "python" in reqs[0].skills

# --- retrieval ---
def test_scores_every_matching_unit(): assert len(score_evidence(parse_evidence(CV), JD)) >= 3
def test_empty_overlap_has_no_evidence(): assert score_evidence(parse_evidence("cooking baking"), "kubernetes terraform") == []

# --- verification gate ---
def test_new_number_blocked(): assert check_numbers("Improved by 99%", number_allowlist(CV)) == ["99%"]
def test_existing_number_allowed(): assert not check_numbers("Improved by 30%", number_allowlist(CV))
def test_new_entity_blocked(): assert "Kubernetes" in check_entities("Used Kubernetes daily", entity_allowlist(CV))
def test_existing_entity_allowed(): assert not check_entities("Used Selenium daily", entity_allowlist(CV))
def test_provenance_verbatim(): assert provenance("Reduced regression time by 30%.", CV) == "verbatim"
def test_provenance_rephrased():
    assert provenance("Added tests to CI pipelines and tested REST APIs with Postman.", CV) == "rephrased"
def test_provenance_reframed(): assert provenance("A testing professional.", CV) == "reframed"
def test_gate_blocks_and_records():
    units = [TailoredUnit(id="t-1", section="summary", text="Scaled Kubernetes to 99 clusters.", provenance="reframed", evidence_ids=["ev-2"])]
    passed, blocked = run_gate(units, {"ev-2": "Built Selenium tests."}, CV)
    assert not passed and blocked[0].gate == "number-allowlist"
def test_gate_blocks_unentailed():
    units = [TailoredUnit(id="t-1", section="summary", text="engineer.", provenance="reframed", evidence_ids=["ev-9"])]
    passed, blocked = run_gate(units, {}, CV)
    assert not passed and blocked[0].gate == "entailment"

# --- pipeline ---
def test_coverage_matrix_shape():
    cov = tailor_cv(CV, JD).coverage
    assert cov.hard_total >= 1 and 0 <= cov.hard_covered <= cov.hard_total
    assert all(row.status in {"covered", "partial", "missing"} for row in cov.rows)
def test_covered_and_missing_skills_split():
    row = tailor_cv(CV, JD).coverage.rows[0]
    assert not set(row.covered_skills) & set(row.missing_skills)
def test_reports_gap_not_inserted():
    result = tailor_cv(CV, JD)
    assert "playwright" in result.gaps
    assert "Playwright" not in result.tailored_cv
def test_every_unit_has_evidence_and_provenance():
    for unit in tailor_cv(CV, JD).tailored_units:
        assert unit.evidence_ids
        assert unit.provenance in {"verbatim", "rephrased", "reframed"}
def test_no_duplicate_sentences():
    texts = [u.text for u in tailor_cv(CV, JD).tailored_units]
    assert len(texts) == len(set(texts))
def test_page_budget_trims():
    one = tailor_cv(BIG_CV, JD, page_budget=1)
    two = tailor_cv(BIG_CV, JD, page_budget=2)
    assert len(two.tailored_cv) > len(one.tailored_cv)
    assert any(c.kind == "omit" for c in one.change_log)
def test_kubernetes_never_inserted():
    jd = JD + "\nMust have hands-on Kubernetes and 12 years of distributed systems experience."
    result = tailor_cv(CV, jd)
    assert "kubernetes" in result.gaps
    assert "kubernetes" not in result.tailored_cv.lower()
def test_parseability_checks_run():
    checks = {c.id: c.status for c in check_parseability(CV)}
    assert checks["layout"] == "pass" and checks["contact"] == "pass"
def test_parseability_flags_tables():
    checks = {c.id: c.status for c in check_parseability("Name | Role | Years\nA | B | C")}
    assert checks["layout"] == "fail"

# --- batch ranking ---
def test_rank_orders_best_fit_first():
    ranked = rank_jobs(CV, [
        "We need a Kubernetes and Terraform expert with 10 years of distributed systems.",
        JD,
    ])
    assert ranked[0].index == 1 and ranked[0].coverage_ratio > ranked[1].coverage_ratio
def test_rank_reports_gaps():
    ranked = rank_jobs(CV, ["We need a Kubernetes expert."])
    assert "kubernetes" in ranked[0].top_gaps
