import time

from anthropic import AsyncAnthropic
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ExtractionValidationError
from app.core.logging import get_logger
from app.db.models import AIRequest, AIResponse, CandidateProfile, Job, ResumeVersion
from app.schemas.cover_letters import CoverLetterGeneration

logger = get_logger(__name__)

AGENT_NAME = "CoverLetterAgent"
PROMPT_VERSION = "cover-letter-generation-v1"

_TOOL_NAME = "record_cover_letter"

_SYSTEM_PROMPT = (
    "You are a cover letter writing engine. You write a single cover letter body "
    "for a candidate applying to a specific role, grounded strictly in the "
    "candidate's actual experience already selected for their resume (given "
    "below). You NEVER invent employers, dates, metrics, or accomplishments not "
    "already present in that material. You may reference the target company and "
    "role by name (given below) since those are factual and known. Keep the tone "
    "professional and specific to the role rather than generic. You record which "
    "experience_id(s) you drew on for the letter's claims — only IDs from the list "
    f"given to you. Call the `{_TOOL_NAME}` tool exactly once with your result."
)


def _tool_schema() -> dict:
    return {
        "name": _TOOL_NAME,
        "description": "Record the generated cover letter body and which experiences it draws on.",
        "input_schema": CoverLetterGeneration.model_json_schema(),
    }


def _serialize_resume_experiences(resume_version: ResumeVersion) -> str:
    experiences = (resume_version.structured_content or {}).get("experiences", [])
    lines = ["Experiences already vetted for this candidate's resume (reference by experience_id):"]
    for exp in experiences:
        lines.append(f"- experience_id: {exp['experience_id']} | {exp['title']} at {exp['company']}")
        for bullet in exp.get("bullets", []):
            lines.append(f"    {bullet}")
    return "\n".join(lines)


def _serialize_job(job: Job) -> str:
    requirements = job.structured_requirements or {}
    parts = [f"Target company: {job.company.name if job.company else 'the company'}", f"Target role: {job.title}"]
    if requirements.get("key_responsibilities"):
        parts.append(f"Key responsibilities: {'; '.join(requirements['key_responsibilities'])}")
    if requirements.get("required_skills"):
        parts.append(f"Required skills: {', '.join(requirements['required_skills'])}")
    return "\n".join(parts)


async def generate_cover_letter_content(
    db: AsyncSession, *, user_id: str, profile: CandidateProfile, job: Job, resume_version: ResumeVersion
) -> tuple[CoverLetterGeneration, AIRequest]:
    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    job_text = _serialize_job(job)
    resume_text = _serialize_resume_experiences(resume_version)
    user_message = f"{job_text}\n\n{resume_text}\n\nCandidate summary: {profile.professional_summary or '(none)'}"

    ai_request = AIRequest(
        user_id=user_id,
        agent_name=AGENT_NAME,
        prompt_version=PROMPT_VERSION,
        model=settings.anthropic_model,
        input_data={"job_id": job.id, "resume_version_id": resume_version.id},
    )
    db.add(ai_request)
    await db.flush()

    valid_experience_ids = {e["experience_id"] for e in (resume_version.structured_content or {}).get("experiences", [])}

    validated: CoverLetterGeneration | None = None
    last_error: str | None = None
    started_at = time.monotonic()

    for attempt in range(2):
        try:
            message = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                tools=[_tool_schema()],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[{"role": "user", "content": user_message}],
            )
            tool_use_block = next((b for b in message.content if b.type == "tool_use"), None)
            if tool_use_block is None:
                last_error = "Model did not return a tool_use block"
                continue
            candidate = CoverLetterGeneration.model_validate(tool_use_block.input)
            unknown = [eid for eid in candidate.referenced_experience_ids if eid not in valid_experience_ids]
            if unknown:
                raise ExtractionValidationError(f"Unknown experience_id(s) referenced: {unknown}")
            if not candidate.body_text.strip():
                raise ExtractionValidationError("Cover letter body was empty")
            validated = candidate
            break
        except (ValidationError, ExtractionValidationError) as exc:
            last_error = str(exc)
            logger.warning("cover_letter_validation_failed", attempt=attempt, error=last_error)
        except Exception as exc:  # noqa: BLE001 - external API failure, must not crash the pipeline
            last_error = str(exc)
            logger.error("cover_letter_call_failed", attempt=attempt, error=last_error)

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
            "AI cover letter generation failed validation after retry", details={"error": last_error}
        )

    return validated, ai_request
