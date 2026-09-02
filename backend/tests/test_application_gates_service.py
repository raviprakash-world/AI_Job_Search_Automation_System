from app.db.models import Application, ApplicationAnswer, CandidateProfile, CoverLetterVersion, Job, JobMatch, ResumeVersion
from app.services.application_gates_service import (
    check_candidate_readiness,
    check_content_qa,
    check_job_and_duplicate,
    check_match_quality,
    run_all_gates,
)


def _job(status="open") -> Job:
    return Job(title="Backend Engineer", status=status)


def _profile(**overrides) -> CandidateProfile:
    defaults = dict(full_name="Jane Doe", phone="555-1234")
    defaults.update(overrides)
    return CandidateProfile(user_id="u1", **defaults)


def _resume_version(status="ready") -> ResumeVersion:
    return ResumeVersion(version_number=1, status=status)


def _match(fit_score=90.0, hard_disqualifiers=None) -> JobMatch:
    return JobMatch(fit_score=fit_score, hard_disqualifiers=hard_disqualifiers or [])


# --- job & duplicate ---------------------------------------------------------


def test_job_gate_fails_when_job_closed():
    result = check_job_and_duplicate(_job(status="closed"), [])
    assert result.passed is False


def test_job_gate_fails_on_active_duplicate():
    duplicate = Application(status="ready_for_review")
    result = check_job_and_duplicate(_job(), [duplicate])
    assert result.passed is False


def test_job_gate_passes_with_only_terminal_negative_duplicates():
    withdrawn = Application(status="withdrawn")
    rejected = Application(status="rejected")
    result = check_job_and_duplicate(_job(), [withdrawn, rejected])
    assert result.passed is True


# --- candidate readiness ------------------------------------------------------


def test_candidate_gate_fails_without_contact_info():
    profile = _profile(full_name=None, phone=None, location=None)
    result = check_candidate_readiness(profile, _resume_version())
    assert result.passed is False


def test_candidate_gate_fails_when_resume_not_ready():
    result = check_candidate_readiness(_profile(), _resume_version(status="qa_failed"))
    assert result.passed is False


def test_candidate_gate_fails_when_no_resume_version():
    result = check_candidate_readiness(_profile(), None)
    assert result.passed is False


def test_candidate_gate_passes_when_ready():
    result = check_candidate_readiness(_profile(), _resume_version())
    assert result.passed is True


# --- match quality ------------------------------------------------------------


def test_match_gate_fails_without_a_match():
    result = check_match_quality(None, threshold=70, override=False)
    assert result.passed is False


def test_match_gate_fails_below_threshold_without_override():
    result = check_match_quality(_match(fit_score=50.0), threshold=70, override=False)
    assert result.passed is False


def test_match_gate_passes_below_threshold_with_override():
    result = check_match_quality(_match(fit_score=50.0), threshold=70, override=True)
    assert result.passed is True
    assert result.overridden is True


def test_match_gate_fails_on_hard_disqualifier_without_override():
    result = check_match_quality(_match(fit_score=95.0, hard_disqualifiers=["No sponsorship"]), threshold=70, override=False)
    assert result.passed is False


def test_match_gate_passes_on_hard_disqualifier_with_override():
    result = check_match_quality(_match(fit_score=95.0, hard_disqualifiers=["No sponsorship"]), threshold=70, override=True)
    assert result.passed is True
    assert result.overridden is True


def test_match_gate_passes_cleanly_above_threshold_no_override_needed():
    result = check_match_quality(_match(fit_score=95.0), threshold=70, override=False)
    assert result.passed is True
    assert result.overridden is False


# --- content QA -----------------------------------------------------------


def test_content_gate_fails_on_cover_letter_qa_errors():
    cl = CoverLetterVersion(version_number=1, status="qa_failed", qa_report={"errors": ["Company name missing"]})
    result = check_content_qa(cl, [])
    assert result.passed is False


def test_content_gate_fails_on_unreviewed_flagged_answer():
    answer = ApplicationAnswer(question="Salary expectations?", is_grounded=False, reviewed=False)
    result = check_content_qa(None, [answer])
    assert result.passed is False


def test_content_gate_passes_when_flagged_answer_was_reviewed():
    answer = ApplicationAnswer(question="Salary expectations?", is_grounded=False, reviewed=True, answer="I edited this myself")
    result = check_content_qa(None, [answer])
    assert result.passed is True


def test_content_gate_passes_when_all_grounded():
    answer = ApplicationAnswer(question="Notice period?", is_grounded=True, reviewed=False, answer="2 weeks")
    result = check_content_qa(None, [answer])
    assert result.passed is True


# --- combined -----------------------------------------------------------------


def test_run_all_gates_passes_when_everything_is_clean():
    report = run_all_gates(
        job=_job(),
        other_applications_for_job=[],
        profile=_profile(),
        resume_version=_resume_version(),
        job_match=_match(),
        match_threshold=70,
        override_low_match=False,
        cover_letter_version=None,
        answers=[],
    )
    assert report.passed is True
    assert len(report.gates) == 4


def test_run_all_gates_fails_overall_if_any_gate_fails():
    report = run_all_gates(
        job=_job(status="closed"),
        other_applications_for_job=[],
        profile=_profile(),
        resume_version=_resume_version(),
        job_match=_match(),
        match_threshold=70,
        override_low_match=False,
        cover_letter_version=None,
        answers=[],
    )
    assert report.passed is False
