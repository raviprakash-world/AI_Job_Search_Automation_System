import time

from anthropic import AsyncAnthropic
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ExtractionValidationError
from app.core.logging import get_logger
from app.db.models import AIRequest, AIResponse, CandidateProfile, Job
from app.schemas.resumes import ResumeGeneration

logger = get_logger(__name__)

AGENT_NAME = "ResumeAgent"
PROMPT_VERSION = "resume-generation-v1"

_TOOL_NAME = "record_resume_generation"

_SYSTEM_PROMPT = (
    "You are a resume tailoring engine. You write a professional summary and "
    "tailored bullet points for a candidate's resume, grounded strictly in the "
    "candidate's actual work history provided below. You NEVER invent employers, "
    "job titles, dates, degrees, skills, or metrics that are not already present "
    "in the source material. You may rephrase, reorder, emphasize, and summarize "
    "truthful information, and prioritize skills/experience relevant to the target "
    "role when one is given — but every bullet must be traceable to that "
    "experience's original responsibilities/achievements text. Use past tense for "
    "roles that have ended and present tense for the current role. You do not "
    "output company names, job titles, dates, or degrees yourself — you only "
    "reference experiences/skills/projects/certifications by the IDs given to you. "
    f"Call the `{_TOOL_NAME}` tool exactly once with your selections."
)


def _tool_schema() -> dict:
    return {
        "name": _TOOL_NAME,
        "description": "Record the tailored resume content: summary, skill selection, and per-experience bullets.",
        "input_schema": ResumeGeneration.model_json_schema(),
    }


def _serialize_profile(profile: CandidateProfile) -> str:
    lines = [f"Professional summary on file: {profile.professional_summary or '(none)'}"]

    lines.append("\nSkills (choose only from this list):")
    for skill in profile.skills:
        lines.append(f"- {skill.name}")

    lines.append("\nExperiences (reference by experience_id, do not restate company/title/dates):")
    for exp in profile.experiences:
        lines.append(
            f"- experience_id: {exp.id} | {exp.title} at {exp.company} "
            f"({exp.start_date or '?'} to {'present' if exp.is_current else (exp.end_date or '?')})"
        )
        for r in exp.responsibilities:
            lines.append(f"    responsibility: {r}")
        for a in exp.achievements:
            lines.append(f"    achievement: {a}")

    if profile.projects:
        lines.append("\nProjects (reference by project_id):")
        for project in profile.projects:
            lines.append(f"- project_id: {project.id} | {project.name}: {project.description or ''}")

    if profile.certifications:
        lines.append("\nCertifications (reference by certification_id):")
        for cert in profile.certifications:
            lines.append(f"- certification_id: {cert.id} | {cert.name}")

    return "\n".join(lines)


def _serialize_job(job: Job) -> str:
    requirements = job.structured_requirements or {}
    parts = [f"Target role: {job.title}"]
    if requirements.get("required_skills"):
        parts.append(f"Required skills: {', '.join(requirements['required_skills'])}")
    if requirements.get("preferred_skills"):
        parts.append(f"Preferred skills: {', '.join(requirements['preferred_skills'])}")
    if requirements.get("key_responsibilities"):
        parts.append(f"Key responsibilities: {'; '.join(requirements['key_responsibilities'])}")
    return "\n".join(parts)


async def generate_resume_content(
    db: AsyncSession, *, user_id: str, profile: CandidateProfile, job: Job | None
) -> tuple[ResumeGeneration, AIRequest]:
    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    profile_text = _serialize_profile(profile)
    job_text = _serialize_job(job) if job else "No specific target role — write a strong general-purpose resume."
    user_message = f"{job_text}\n\n--- Candidate profile ---\n{profile_text}"

    ai_request = AIRequest(
        user_id=user_id,
        agent_name=AGENT_NAME,
        prompt_version=PROMPT_VERSION,
        model=settings.anthropic_model,
        input_data={"job_id": job.id if job else None, "profile_text": profile_text},
    )
    db.add(ai_request)
    await db.flush()

    validated: ResumeGeneration | None = None
    last_error: str | None = None
    started_at = time.monotonic()

    for attempt in range(2):
        try:
            message = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=4096,
                system=_SYSTEM_PROMPT,
                tools=[_tool_schema()],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[{"role": "user", "content": user_message}],
            )
            tool_use_block = next((b for b in message.content if b.type == "tool_use"), None)
            if tool_use_block is None:
                last_error = "Model did not return a tool_use block"
                continue
            candidate = ResumeGeneration.model_validate(tool_use_block.input)
            _validate_grounded_references(candidate, profile)
            validated = candidate
            break
        except (ValidationError, ExtractionValidationError) as exc:
            last_error = str(exc)
            logger.warning("resume_generation_validation_failed", attempt=attempt, error=last_error)
        except Exception as exc:  # noqa: BLE001 - external API failure, must not crash the pipeline
            last_error = str(exc)
            logger.error("resume_generation_call_failed", attempt=attempt, error=last_error)

    latency_ms = int((time.monotonic() - started_at) * 1000)

    response = AIResponse(
        request_id=ai_request.id,
        output_data=validated.model_dump(mode="json") if validated else {},
        validation_status="valid" if validated else "invalid",
        error=None if validated else last_error,
        latency_ms=latency_ms,
    )
    db.add(response)
    await db.commit()
    await db.refresh(ai_request)

    if validated is None:
        raise ExtractionValidationError(
            "AI resume generation failed validation after retry", details={"error": last_error}
        )

    return validated, ai_request


def _validate_grounded_references(candidate: ResumeGeneration, profile: CandidateProfile) -> None:
    """The model may only reference IDs/skill names that actually exist in the profile.

    This is the hard guardrail described in the Phase 3 plan — it is not optional
    and is checked in addition to (not instead of) Pydantic schema validation.
    """
    valid_experience_ids = {e.id for e in profile.experiences}
    valid_skill_names = {s.name.strip().lower() for s in profile.skills}
    valid_project_ids = {p.id for p in profile.projects}
    valid_cert_ids = {c.id for c in profile.certifications}

    for selection in candidate.experience_selections:
        if selection.experience_id not in valid_experience_ids:
            raise ExtractionValidationError(f"Unknown experience_id referenced: {selection.experience_id}")

    for name in candidate.selected_skill_names:
        if name.strip().lower() not in valid_skill_names:
            raise ExtractionValidationError(f"Unknown skill referenced: {name}")

    for project_id in candidate.selected_project_ids:
        if project_id not in valid_project_ids:
            raise ExtractionValidationError(f"Unknown project_id referenced: {project_id}")

    for cert_id in candidate.selected_certification_ids:
        if cert_id not in valid_cert_ids:
            raise ExtractionValidationError(f"Unknown certification_id referenced: {cert_id}")

    if not candidate.experience_selections:
        raise ExtractionValidationError("Resume generation selected zero experiences")
