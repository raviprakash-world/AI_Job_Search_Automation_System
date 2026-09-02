from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.db.models import CandidateProfile, Job, JobMatch, User, UserPreference
from app.services import profile_service

DEFAULT_SCORING_WEIGHTS = {
    "skills": 0.35,
    "experience": 0.20,
    "location": 0.15,
    "seniority": 0.15,
    "salary": 0.15,
}

DEFAULT_SHORTLIST_THRESHOLDS = {"excellent": 90, "strong": 80, "review": 70}

_NO_SPONSORSHIP_PHRASES = ("no sponsorship", "not sponsor", "without sponsorship", "unable to sponsor")
_NEEDS_SPONSORSHIP_PHRASES = ("require sponsorship", "requires sponsorship", "needs sponsorship", "h1b sponsorship needed")

_SENIORITY_ORDER = ["intern", "junior", "mid", "senior", "staff", "principal", "lead", "director"]


# --- Pure scoring functions (unit-testable without a DB) ----------------------


def score_skills(
    profile_skill_names: list[str], required_skills: list[str], preferred_skills: list[str]
) -> tuple[float, list[str], list[str], list[str]] | None:
    if not required_skills and not preferred_skills:
        return None

    profile_set = {s.strip().lower() for s in profile_skill_names if s.strip()}
    required_set = {s.strip().lower() for s in required_skills if s.strip()}
    preferred_set = {s.strip().lower() for s in preferred_skills if s.strip()}

    matched_required = sorted(required_set & profile_set)
    matched_preferred = sorted(preferred_set & profile_set)
    missing_required = sorted(required_set - profile_set)

    required_score = (len(matched_required) / len(required_set)) if required_set else 1.0
    preferred_score = (len(matched_preferred) / len(preferred_set)) if preferred_set else 1.0
    # Required skills matter far more than preferred ones.
    score = (required_score * 0.8 + preferred_score * 0.2) * 100
    return score, matched_required, matched_preferred, missing_required


def total_years_experience(experiences: list) -> float:
    total_days = 0
    for exp in experiences:
        if not exp.start_date:
            continue
        end = exp.end_date or date.today()
        total_days += max((end - exp.start_date).days, 0)
    return round(total_days / 365.25, 1)


def score_experience(total_years: float, min_years: int | None, max_years: int | None) -> tuple[float, str] | None:
    if min_years is None:
        return None
    if total_years >= min_years:
        return 100.0, f"Meets the {min_years}+ years experience requirement ({total_years} years)"
    shortfall = min_years - total_years
    score = max(0.0, 100 - shortfall * 20)
    return score, f"Posting asks for {min_years}+ years; profile shows {total_years} years"


def score_location(
    job_location: str | None,
    remote_status: str | None,
    preferred_locations: list[str],
    profile_location: str | None,
    remote_preference: str | None,
) -> tuple[float, str] | None:
    if not job_location and (remote_status in (None, "unknown")):
        return None

    normalized_preferred = {p.strip().lower() for p in preferred_locations if p.strip()}
    normalized_job_location = (job_location or "").strip().lower()

    if remote_status == "remote" and remote_preference in (None, "remote", "hybrid", "flexible"):
        return 100.0, "Remote position matches your remote preference"

    if normalized_job_location and (
        normalized_job_location in normalized_preferred
        or (profile_location and profile_location.strip().lower() == normalized_job_location)
    ):
        return 100.0, f"Location ({job_location}) matches your preferences"

    if remote_status == "hybrid":
        return 60.0, "Hybrid role — partial location match"

    if normalized_job_location:
        return 20.0, f"Location ({job_location}) does not match your stated preferences"

    return None


def score_seniority(job_seniority: str | None, total_years: float) -> tuple[float, str] | None:
    if not job_seniority:
        return None
    job_level = job_seniority.strip().lower()
    if job_level not in _SENIORITY_ORDER:
        return None

    if total_years < 2:
        profile_level = "junior"
    elif total_years < 5:
        profile_level = "mid"
    elif total_years < 8:
        profile_level = "senior"
    else:
        profile_level = "staff"

    job_idx = _SENIORITY_ORDER.index(job_level)
    profile_idx = _SENIORITY_ORDER.index(profile_level)
    distance = abs(job_idx - profile_idx)

    if distance == 0:
        return 100.0, f"Seniority level ({job_seniority}) matches your experience"
    if distance == 1:
        return 60.0, f"Seniority level ({job_seniority}) is close to your experience level"
    return 20.0, f"Seniority level ({job_seniority}) may not match your experience level"


def score_salary(
    profile_min: int | None, profile_max: int | None, job_min: int | None, job_max: int | None
) -> tuple[float, str] | None:
    if profile_min is None and profile_max is None:
        return None
    if job_min is None and job_max is None:
        return None

    p_min = profile_min if profile_min is not None else 0
    p_max = profile_max if profile_max is not None else float("inf")
    j_min = job_min if job_min is not None else 0
    j_max = job_max if job_max is not None else float("inf")

    overlap = min(p_max, j_max) - max(p_min, j_min)
    if overlap >= 0:
        return 100.0, "Salary range overlaps with your expectations"
    return 30.0, "Salary range may not meet your expectations"


def check_work_authorization_disqualifier(profile_work_auth: str | None, job_requirement_text: str | None) -> str | None:
    """Conservative keyword heuristic — only flags on clear, explicit phrasing to avoid
    fabricating a mismatch conclusion the text doesn't actually support."""
    if not profile_work_auth or not job_requirement_text:
        return None

    job_text = job_requirement_text.lower()
    profile_text = profile_work_auth.lower()

    job_says_no_sponsorship = any(phrase in job_text for phrase in _NO_SPONSORSHIP_PHRASES)
    profile_needs_sponsorship = any(phrase in profile_text for phrase in _NEEDS_SPONSORSHIP_PHRASES)

    if job_says_no_sponsorship and profile_needs_sponsorship:
        return "Posting states it cannot sponsor work authorization, which conflicts with your stated profile"
    return None


def aggregate_score(dimension_scores: dict[str, float], weights: dict[str, float]) -> float:
    available = {dim: score for dim, score in dimension_scores.items() if score is not None}
    if not available:
        return 0.0
    relevant_weights = {dim: weights.get(dim, DEFAULT_SCORING_WEIGHTS.get(dim, 0)) for dim in available}
    total_weight = sum(relevant_weights.values()) or 1.0
    return round(sum(available[dim] * relevant_weights[dim] for dim in available) / total_weight, 1)


# --- DB-backed orchestration ---------------------------------------------------


async def _get_or_create_preference(db: AsyncSession, user_id: str) -> UserPreference:
    pref = await db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
    if pref is None:
        pref = UserPreference(user_id=user_id)
        db.add(pref)
        await db.flush()
    return pref


async def compute_match(db: AsyncSession, user: User, job: Job) -> JobMatch:
    profile: CandidateProfile = await profile_service.get_profile_by_user(db, user.id)
    preference = await _get_or_create_preference(db, user.id)
    weights = preference.scoring_weights or DEFAULT_SCORING_WEIGHTS

    requirements = job.structured_requirements or {}
    total_years = total_years_experience(profile.experiences)

    dimension_results: dict[str, tuple[float, str] | tuple[float, list, list, list] | None] = {}

    dimension_results["skills"] = score_skills(
        [s.name for s in profile.skills], requirements.get("required_skills", []), requirements.get("preferred_skills", [])
    )
    dimension_results["experience"] = score_experience(
        total_years, requirements.get("min_years_experience"), requirements.get("max_years_experience")
    )
    dimension_results["location"] = score_location(
        job.location, job.remote_status, profile.preferred_locations, profile.location, profile.remote_preference
    )
    dimension_results["seniority"] = score_seniority(requirements.get("seniority_level"), total_years)
    dimension_results["salary"] = score_salary(
        profile.salary_expectation_min, profile.salary_expectation_max, job.salary_min, job.salary_max
    )

    dimension_scores: dict[str, float | None] = {}
    strong_matches: list[str] = []
    gaps: list[str] = []

    for dim, result in dimension_results.items():
        if result is None:
            dimension_scores[dim] = None
            continue
        if dim == "skills":
            score, matched_required, matched_preferred, missing_required = result
            dimension_scores[dim] = score
            strong_matches.extend(f"Has required skill: {s}" for s in matched_required[:5])
            strong_matches.extend(f"Has preferred skill: {s}" for s in matched_preferred[:3])
            gaps.extend(f"Missing required skill: {s}" for s in missing_required[:5])
        else:
            score, note = result
            dimension_scores[dim] = score
            if score >= 80:
                strong_matches.append(note)
            elif score < 60:
                gaps.append(note)

    hard_disqualifiers = []
    work_auth_issue = check_work_authorization_disqualifier(
        profile.work_authorization, requirements.get("work_authorization_requirements")
    )
    if work_auth_issue:
        hard_disqualifiers.append(work_auth_issue)

    fit_score = aggregate_score(dimension_scores, weights)
    if hard_disqualifiers:
        fit_score = min(fit_score, 20.0)

    if fit_score >= 85:
        summary = f"{fit_score:.0f}% match — strong overlap on {', '.join(strong_matches[:2]) or 'your profile'}."
    elif gaps:
        summary = f"{fit_score:.0f}% match. {gaps[0]}."
    else:
        summary = f"{fit_score:.0f}% match based on your Master Profile."
    if hard_disqualifiers:
        summary = f"{summary} Flagged: {hard_disqualifiers[0]}."

    existing = await db.scalar(select(JobMatch).where(JobMatch.job_id == job.id, JobMatch.user_id == user.id))
    if existing is None:
        existing = JobMatch(job_id=job.id, user_id=user.id)
        db.add(existing)

    existing.fit_score = fit_score
    existing.dimension_scores = dimension_scores
    existing.hard_disqualifiers = hard_disqualifiers
    existing.strong_matches = strong_matches
    existing.gaps = gaps
    existing.summary = summary
    existing.scoring_weights_snapshot = weights
    existing.computed_at = utcnow()

    await db.commit()
    await db.refresh(existing)
    return existing
