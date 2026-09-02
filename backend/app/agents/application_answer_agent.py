import time

from anthropic import AsyncAnthropic
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ExtractionValidationError
from app.core.logging import get_logger
from app.db.models import AIRequest, AIResponse, CandidateProfile, Job
from app.schemas.applications import ApplicationAnswerGeneration

logger = get_logger(__name__)

AGENT_NAME = "ApplicationAnswerAgent"
PROMPT_VERSION = "application-answers-v1"

_TOOL_NAME = "record_application_answers"

_SYSTEM_PROMPT = (
    "You are an application question answering engine. For each question, you "
    "answer truthfully using ONLY the candidate profile facts given below. If a "
    "question cannot be answered truthfully from the given profile (e.g. it asks "
    "about something not present, like salary history when none is recorded, or "
    "something genuinely subjective the candidate must decide themselves), you "
    "MUST set is_grounded to false and give a clear flag_reason instead of "
    "guessing or inventing a plausible-sounding answer. You must return exactly "
    "one result per question, in the same order the questions were given. Call "
    f"the `{_TOOL_NAME}` tool exactly once with your results."
)


def _tool_schema() -> dict:
    return {
        "name": _TOOL_NAME,
        "description": "Record an answer (or a flag) for each application question, in order.",
        "input_schema": ApplicationAnswerGeneration.model_json_schema(),
    }


def _serialize_profile(profile: CandidateProfile) -> str:
    lines = [
        f"Full name: {profile.full_name or '(not set)'}",
        f"Location: {profile.location or '(not set)'}",
        f"Work authorization: {profile.work_authorization or '(not set)'}",
        f"Notice period: {profile.notice_period or '(not set)'}",
        f"Remote preference: {profile.remote_preference or '(not set)'}",
        f"Target roles: {', '.join(profile.target_roles) or '(not set)'}",
        f"Professional summary: {profile.professional_summary or '(not set)'}",
        f"Skills: {', '.join(s.name for s in profile.skills) or '(none)'}",
    ]
    for exp in profile.experiences:
        lines.append(f"Experience: {exp.title} at {exp.company} ({exp.start_date} to {exp.end_date or 'present'})")
    return "\n".join(lines)


def _serialize_job(job: Job) -> str:
    return f"Target role: {job.title} at {job.company.name if job.company else 'the company'}"


async def generate_application_answers(
    db: AsyncSession, *, user_id: str, profile: CandidateProfile, job: Job, questions: list[str]
) -> tuple[ApplicationAnswerGeneration, AIRequest]:
    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    questions_text = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    user_message = f"{_serialize_job(job)}\n\nCandidate profile:\n{_serialize_profile(profile)}\n\nQuestions:\n{questions_text}"

    ai_request = AIRequest(
        user_id=user_id,
        agent_name=AGENT_NAME,
        prompt_version=PROMPT_VERSION,
        model=settings.anthropic_model,
        input_data={"job_id": job.id, "questions": questions},
    )
    db.add(ai_request)
    await db.flush()

    validated: ApplicationAnswerGeneration | None = None
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
            candidate = ApplicationAnswerGeneration.model_validate(tool_use_block.input)
            if len(candidate.results) != len(questions):
                raise ExtractionValidationError(
                    f"Expected {len(questions)} answers, got {len(candidate.results)}"
                )
            validated = candidate
            break
        except (ValidationError, ExtractionValidationError) as exc:
            last_error = str(exc)
            logger.warning("application_answer_validation_failed", attempt=attempt, error=last_error)
        except Exception as exc:  # noqa: BLE001 - external API failure, must not crash the pipeline
            last_error = str(exc)
            logger.error("application_answer_call_failed", attempt=attempt, error=last_error)

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
            "AI application answer generation failed validation after retry", details={"error": last_error}
        )

    return validated, ai_request
