from pathlib import Path

from app.db.models import CandidateProfile, Job
from app.schemas.resumes import QAReport, StructuredResumeContent
from app.services.document_parsing import parse_docx
from app.services.text_grounding import find_unsupported_numbers

_MIN_WORD_COUNT = 150
_MAX_WORD_COUNT = 1400


def _check_output_integrity(content: StructuredResumeContent, rendered_text: str) -> list[str]:
    errors: list[str] = []

    if content.email and content.email not in rendered_text:
        errors.append("Email address did not survive rendering")
    if content.phone and content.phone not in rendered_text:
        errors.append("Phone number did not survive rendering")
    if content.full_name and content.full_name not in rendered_text:
        errors.append("Candidate name did not survive rendering")

    for exp in content.experiences:
        if exp.company not in rendered_text:
            errors.append(f"Company name '{exp.company}' missing from rendered resume")

    if content.experiences and "Experience" not in rendered_text:
        errors.append("Experience section header missing from rendered resume")

    return errors


def _check_length(rendered_text: str) -> tuple[int, list[str]]:
    warnings: list[str] = []
    word_count = len(rendered_text.split())
    if word_count < _MIN_WORD_COUNT:
        warnings.append(f"Resume is quite short ({word_count} words) — consider adding more detail")
    elif word_count > _MAX_WORD_COUNT:
        warnings.append(f"Resume is long ({word_count} words) — likely more than 2 pages")
    return word_count, warnings


def _check_ats_coverage(content: StructuredResumeContent, job: Job | None) -> tuple[float | None, list[str], list[str]]:
    if job is None:
        return None, [], []
    required = (job.structured_requirements or {}).get("required_skills", [])
    if not required:
        return None, [], []

    haystack = (
        " ".join(content.skills) + " " + " ".join(b for exp in content.experiences for b in exp.bullets)
    ).lower()

    matched = [skill for skill in required if skill.lower() in haystack]
    missing = [skill for skill in required if skill.lower() not in haystack]
    coverage = round(len(matched) / len(required) * 100, 1)
    return coverage, matched, missing


def _check_unsupported_metrics(content: StructuredResumeContent, profile: CandidateProfile) -> list[str]:
    source_by_id = {
        e.id: " ".join(e.responsibilities) + " " + " ".join(e.achievements) for e in profile.experiences
    }
    warnings: list[str] = []

    for exp in content.experiences:
        source_text = source_by_id.get(exp.experience_id, "")
        for bullet in exp.bullets:
            for match in find_unsupported_numbers(bullet, source_text):
                warnings.append(
                    f"Bullet for {exp.company} mentions '{match}', which doesn't appear in your original "
                    "profile text for that role — please verify before using"
                )
    return warnings


def run_qa(
    *, profile: CandidateProfile, content: StructuredResumeContent, docx_path: Path, job: Job | None
) -> QAReport:
    try:
        rendered_text = parse_docx(docx_path)
    except Exception as exc:  # noqa: BLE001
        return QAReport(word_count=0, errors=[f"Generated resume file could not be re-parsed: {exc}"])

    errors = _check_output_integrity(content, rendered_text)
    word_count, length_warnings = _check_length(rendered_text)
    coverage, matched, missing = _check_ats_coverage(content, job)
    metric_warnings = _check_unsupported_metrics(content, profile)

    return QAReport(
        ats_keyword_coverage=coverage,
        matched_keywords=matched,
        missing_keywords=missing,
        word_count=word_count,
        warnings=[*length_warnings, *metric_warnings],
        errors=errors,
    )
