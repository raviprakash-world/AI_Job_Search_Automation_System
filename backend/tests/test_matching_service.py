from datetime import date, timedelta

from app.services.matching_service import (
    aggregate_score,
    check_work_authorization_disqualifier,
    score_experience,
    score_location,
    score_salary,
    score_seniority,
    score_skills,
    total_years_experience,
)


class _Exp:
    def __init__(self, start_date, end_date=None):
        self.start_date = start_date
        self.end_date = end_date


# --- skills ---------------------------------------------------------------


def test_score_skills_returns_none_when_job_lists_no_skills():
    assert score_skills(["Python"], [], []) is None


def test_score_skills_full_match_scores_100():
    result = score_skills(["Python", "SQL"], ["python", "sql"], [])
    score, matched_required, matched_preferred, missing_required = result
    assert score == 100.0
    assert matched_required == ["python", "sql"]
    assert missing_required == []


def test_score_skills_partial_match_flags_missing_required():
    result = score_skills(["Python"], ["python", "kubernetes"], ["docker"])
    score, matched_required, matched_preferred, missing_required = result
    assert matched_required == ["python"]
    assert missing_required == ["kubernetes"]
    assert 0 < score < 100


def test_score_skills_is_case_insensitive():
    result = score_skills(["PYTHON"], ["python"], [])
    assert result[0] == 100.0


# --- experience -------------------------------------------------------------


def test_total_years_experience_sums_durations():
    experiences = [
        _Exp(date.today() - timedelta(days=730), date.today() - timedelta(days=365)),  # 1 year
        _Exp(date.today() - timedelta(days=365), None),  # current, 1 year
    ]
    assert total_years_experience(experiences) == 2.0


def test_score_experience_none_when_job_has_no_requirement():
    assert score_experience(5.0, None, None) is None


def test_score_experience_full_score_when_meets_requirement():
    score, note = score_experience(6.0, 5, None)
    assert score == 100.0
    assert "Meets" in note


def test_score_experience_penalizes_shortfall():
    score, note = score_experience(2.0, 5, None)
    assert score < 100.0
    assert "asks for 5" in note


# --- location -----------------------------------------------------------------


def test_score_location_none_when_no_data():
    assert score_location(None, None, [], None, None) is None


def test_score_location_remote_job_matches_remote_preference():
    score, _ = score_location(None, "remote", [], None, "remote")
    assert score == 100.0


def test_score_location_matches_preferred_locations():
    score, _ = score_location("Austin, TX", "onsite", ["Austin, TX"], None, "onsite")
    assert score == 100.0


def test_score_location_mismatch_scores_low():
    score, _ = score_location("Berlin", "onsite", ["Austin, TX"], "Austin, TX", "onsite")
    assert score == 20.0


# --- seniority ------------------------------------------------------------


def test_score_seniority_none_when_job_level_unknown():
    assert score_seniority(None, 5.0) is None
    assert score_seniority("not-a-level", 5.0) is None


def test_score_seniority_exact_match():
    score, _ = score_seniority("senior", 6.0)
    assert score == 100.0


def test_score_seniority_far_mismatch_scores_low():
    score, _ = score_seniority("principal", 1.0)
    assert score == 20.0


# --- salary ---------------------------------------------------------------


def test_score_salary_none_when_either_side_missing():
    assert score_salary(None, None, 100_000, 120_000) is None
    assert score_salary(100_000, 120_000, None, None) is None


def test_score_salary_overlap_scores_100():
    score, _ = score_salary(100_000, 130_000, 110_000, 150_000)
    assert score == 100.0


def test_score_salary_no_overlap_scores_low():
    score, _ = score_salary(150_000, 180_000, 80_000, 100_000)
    assert score == 30.0


# --- work authorization -----------------------------------------------------


def test_work_auth_disqualifier_needs_explicit_conflict():
    assert check_work_authorization_disqualifier(None, "No sponsorship available") is None
    assert check_work_authorization_disqualifier("Requires sponsorship", None) is None


def test_work_auth_disqualifier_flags_clear_conflict():
    result = check_work_authorization_disqualifier(
        "Requires sponsorship (H1B)", "We are unable to sponsor work visas for this role."
    )
    assert result is not None


def test_work_auth_disqualifier_does_not_flag_ambiguous_text():
    # Vague/unrelated text should never fabricate a conflict.
    assert check_work_authorization_disqualifier("US Citizen", "Great benefits and PTO.") is None


# --- aggregation ------------------------------------------------------------


def test_aggregate_score_ignores_missing_dimensions():
    weights = {"skills": 0.5, "experience": 0.3, "location": 0.2}
    score = aggregate_score({"skills": 100.0, "experience": None, "location": None}, weights)
    assert score == 100.0  # renormalized over only the available dimension


def test_aggregate_score_weights_available_dimensions_proportionally():
    weights = {"skills": 0.5, "experience": 0.5}
    score = aggregate_score({"skills": 100.0, "experience": 0.0}, weights)
    assert score == 50.0


def test_aggregate_score_zero_when_nothing_available():
    assert aggregate_score({"skills": None}, {"skills": 1.0}) == 0.0
