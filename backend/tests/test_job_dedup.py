from app.db.models import Job
from app.services.job_dedup_service import find_matching_job
from app.services.job_normalization import normalize_text


def _job(title: str, location: str | None) -> Job:
    return Job(title=title, normalized_title=normalize_text(title), location=location, company_id="company-1")


def test_exact_normalized_match_is_found():
    existing = [_job("Senior Software Engineer", "Remote")]
    match = find_matching_job(existing, normalize_text("Senior Software Engineer"), "Remote")
    assert match is existing[0]


def test_no_match_when_title_and_location_both_differ():
    existing = [_job("Senior Software Engineer", "Remote")]
    match = find_matching_job(existing, normalize_text("Product Manager"), "New York")
    assert match is None


def test_fuzzy_match_catches_minor_title_variation():
    existing = [_job("Senior Software Engineer", "Remote")]
    match = find_matching_job(existing, normalize_text("Sr. Software Engineer"), "Remote")
    assert match is existing[0]


def test_fuzzy_match_requires_same_location():
    existing = [_job("Senior Software Engineer", "Remote")]
    match = find_matching_job(existing, normalize_text("Sr. Software Engineer"), "New York")
    assert match is None


def test_dissimilar_titles_are_not_merged():
    existing = [_job("Senior Software Engineer", "Remote")]
    match = find_matching_job(existing, normalize_text("Marketing Manager"), "Remote")
    assert match is None


def test_empty_existing_list_returns_none():
    assert find_matching_job([], normalize_text("Engineer"), "Remote") is None
