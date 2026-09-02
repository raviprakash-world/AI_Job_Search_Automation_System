from app.db.models import Application, ApplicationAnswer, CandidateProfile, CoverLetterVersion, Job, JobMatch, ResumeVersion
from app.schemas.applications import GateReport, GateResult

ACTIVE_APPLICATION_STATUSES = {"preparing", "ready_for_review", "approved", "submitted", "interview", "offer"}


def check_job_and_duplicate(job: Job, other_applications_for_job: list[Application]) -> GateResult:
    if job.status != "open":
        return GateResult(name="job_valid", passed=False, message="This job is no longer marked open")

    active_duplicates = [a for a in other_applications_for_job if a.status in ACTIVE_APPLICATION_STATUSES]
    if active_duplicates:
        return GateResult(
            name="job_valid",
            passed=False,
            message="You already have an active application tracked for this job",
        )
    return GateResult(name="job_valid", passed=True, message="Job is open and not already applied to")


def check_candidate_readiness(profile: CandidateProfile, resume_version: ResumeVersion | None) -> GateResult:
    if not profile.full_name or not (profile.phone or profile.location):
        return GateResult(
            name="candidate_ready", passed=False, message="Your Master Profile is missing basic contact info"
        )
    if resume_version is None or resume_version.status != "ready":
        return GateResult(
            name="candidate_ready", passed=False, message="Selected resume version is not in a ready state"
        )
    return GateResult(name="candidate_ready", passed=True, message="Profile and resume are ready")


def check_match_quality(job_match: JobMatch | None, threshold: float, override: bool) -> GateResult:
    if job_match is None:
        return GateResult(
            name="match_quality", passed=False, message="No fit-score analysis found for this job yet"
        )

    if job_match.hard_disqualifiers and not override:
        return GateResult(
            name="match_quality",
            passed=False,
            message=f"Hard disqualifier flagged: {job_match.hard_disqualifiers[0]}",
        )

    if job_match.fit_score < threshold:
        if override:
            return GateResult(
                name="match_quality",
                passed=True,
                message=f"Fit score {job_match.fit_score:.0f}% is below your {threshold:.0f}% threshold — proceeding on override",
                overridden=True,
            )
        return GateResult(
            name="match_quality",
            passed=False,
            message=f"Fit score {job_match.fit_score:.0f}% is below your configured {threshold:.0f}% threshold",
        )

    overridden = bool(job_match.hard_disqualifiers) and override
    message = "Match quality meets your threshold"
    if overridden:
        message = f"Hard disqualifier overridden: {job_match.hard_disqualifiers[0]}"
    return GateResult(name="match_quality", passed=True, message=message, overridden=overridden)


def check_content_qa(cover_letter_version: CoverLetterVersion | None, answers: list[ApplicationAnswer]) -> GateResult:
    if cover_letter_version is not None:
        errors = (cover_letter_version.qa_report or {}).get("errors", [])
        if errors:
            return GateResult(name="content_qa", passed=False, message=f"Cover letter QA failed: {errors[0]}")

    unreviewed_flags = [a for a in answers if not a.is_grounded and not a.reviewed]
    if unreviewed_flags:
        return GateResult(
            name="content_qa",
            passed=False,
            message=f"{len(unreviewed_flags)} application answer(s) need your review before proceeding",
        )
    return GateResult(name="content_qa", passed=True, message="Content QA passed")


def run_all_gates(
    *,
    job: Job,
    other_applications_for_job: list[Application],
    profile: CandidateProfile,
    resume_version: ResumeVersion | None,
    job_match: JobMatch | None,
    match_threshold: float,
    override_low_match: bool,
    cover_letter_version: CoverLetterVersion | None,
    answers: list[ApplicationAnswer],
) -> GateReport:
    gates = [
        check_job_and_duplicate(job, other_applications_for_job),
        check_candidate_readiness(profile, resume_version),
        check_match_quality(job_match, match_threshold, override_low_match),
        check_content_qa(cover_letter_version, answers),
    ]
    return GateReport(gates=gates, passed=all(g.passed for g in gates))
