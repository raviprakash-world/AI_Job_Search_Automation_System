from pathlib import Path

from app.db.models import CandidateProfile, Job
from app.schemas.cover_letters import CoverLetterGeneration
from app.schemas.resumes import QAReport
from app.services.document_parsing import parse_docx
from app.services.text_grounding import find_unsupported_numbers

_MIN_WORD_COUNT = 100
_MAX_WORD_COUNT = 600


def _check_integrity(
    rendered_text: str, *, full_name: str | None, email: str | None, phone: str | None, company_name: str
) -> list[str]:
    errors = []
    if full_name and full_name not in rendered_text:
        errors.append("Candidate name did not survive rendering")
    if email and email not in rendered_text:
        errors.append("Email address did not survive rendering")
    if phone and phone not in rendered_text:
        errors.append("Phone number did not survive rendering")
    if company_name not in rendered_text:
        errors.append(f"Target company name '{company_name}' missing from rendered cover letter")
    return errors


def _check_length(rendered_text: str) -> tuple[int, list[str]]:
    word_count = len(rendered_text.split())
    warnings = []
    if word_count < _MIN_WORD_COUNT:
        warnings.append(f"Cover letter is quite short ({word_count} words)")
    elif word_count > _MAX_WORD_COUNT:
        warnings.append(f"Cover letter is long ({word_count} words) — consider tightening it")
    return word_count, warnings


def _check_unsupported_metrics(generation: CoverLetterGeneration, profile: CandidateProfile) -> list[str]:
    referenced_ids = set(generation.referenced_experience_ids)
    source_text = " ".join(
        " ".join(e.responsibilities) + " " + " ".join(e.achievements)
        for e in profile.experiences
        if e.id in referenced_ids
    )
    warnings = []
    for match in find_unsupported_numbers(generation.body_text, source_text):
        warnings.append(f"Cover letter mentions '{match}', which doesn't appear in the referenced experience text")
    return warnings


def _check_ats_coverage(body_text: str, job: Job | None) -> tuple[float | None, list[str], list[str]]:
    if job is None:
        return None, [], []
    required = (job.structured_requirements or {}).get("required_skills", [])
    if not required:
        return None, [], []
    haystack = body_text.lower()
    matched = [s for s in required if s.lower() in haystack]
    missing = [s for s in required if s.lower() not in haystack]
    return round(len(matched) / len(required) * 100, 1), matched, missing


def run_qa(
    *,
    profile: CandidateProfile,
    generation: CoverLetterGeneration,
    docx_path: Path,
    job: Job | None,
    full_name: str | None,
    email: str | None,
    phone: str | None,
    company_name: str,
) -> QAReport:
    try:
        rendered_text = parse_docx(docx_path)
    except Exception as exc:  # noqa: BLE001
        return QAReport(word_count=0, errors=[f"Generated cover letter file could not be re-parsed: {exc}"])

    errors = _check_integrity(rendered_text, full_name=full_name, email=email, phone=phone, company_name=company_name)
    word_count, length_warnings = _check_length(rendered_text)
    coverage, matched, missing = _check_ats_coverage(generation.body_text, job)
    metric_warnings = _check_unsupported_metrics(generation, profile)

    return QAReport(
        ats_keyword_coverage=coverage,
        matched_keywords=matched,
        missing_keywords=missing,
        word_count=word_count,
        warnings=[*length_warnings, *metric_warnings],
        errors=errors,
    )
