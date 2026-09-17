from cv_tailor.guardrails import unsupported_claims
from cv_tailor.pipeline import tailor_cv
from cv_tailor.retrieval import retrieve
from cv_tailor.text import keywords, sections, tokens

CV = """CHANDRA QA ENGINEER

SUMMARY
QA engineer experienced in API testing and test automation.

EXPERIENCE
Built Selenium and Python regression tests for web applications.\nReduced regression time by 30%.\nTested REST APIs with Postman and added tests to CI pipelines.
"""
JD = """We need a QA automation engineer skilled in Python, Selenium, REST API testing, CI/CD, Playwright, and performance testing. The engineer will own regression quality."""

def test_tokenize_normalizes_case(): assert "python" in tokens("PYTHON")
def test_keywords_drop_stopwords(): assert "the" not in keywords("the Python engineer")
def test_sections_split_cv(): assert len(sections(CV)) >= 3
def test_retrieval_returns_evidence(): assert retrieve(CV, JD)
def test_retrieval_rank_has_overlap(): assert retrieve(CV, JD)[0].matched_terms
def test_retrieval_ids_are_stable(): assert retrieve(CV, JD)[0].id.startswith("cv-")
def test_match_is_bounded(): assert 0 <= tailor_cv(CV, JD).match_report.score <= 100
def test_reports_known_skill(): assert "python" in tailor_cv(CV, JD).match_report.matched_keywords
def test_reports_missing_skill(): assert "playwright" in tailor_cv(CV, JD).gaps
def test_does_not_insert_gap(): assert "Playwright" not in tailor_cv(CV, JD).tailored_cv
def test_preserves_base_cv(): assert CV.strip() in tailor_cv(CV, JD).tailored_cv
def test_change_log_has_evidence(): assert tailor_cv(CV, JD).change_log[0].evidence_ids
def test_warns_about_gap_policy(): assert any("not inserted" in w for w in tailor_cv(CV, JD).warnings)
def test_new_number_is_flagged(): assert unsupported_claims("Improved by 99%", CV)
def test_existing_number_is_allowed(): assert not unsupported_claims("Improved by 30%", CV)
def test_empty_overlap_has_no_evidence(): assert retrieve("cooking baking", "kubernetes terraform") == []
def test_coverage_is_bounded(): assert 0 <= tailor_cv(CV, JD).match_report.evidence_coverage <= 1
def test_tailored_summary_is_grounded():
    result = tailor_cv(CV, JD)
    assert "Built Selenium and Python" in result.tailored_cv or "QA engineer experienced" in result.tailored_cv
