import time

from anthropic import AsyncAnthropic
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ExtractionValidationError
from app.core.logging import get_logger
from app.db.models import AIRequest, AIResponse
from app.schemas.jobs import JobRequirements

logger = get_logger(__name__)

AGENT_NAME = "JobAnalysisAgent"
PROMPT_VERSION = "job-analysis-v1"
MAX_INPUT_CHARS = 15_000

_TOOL_NAME = "record_job_requirements"

_SYSTEM_PROMPT = (
    "You are a job-posting analysis engine. You extract ONLY requirements that are "
    "explicitly stated or clearly implied by the posting text. You NEVER invent, "
    "infer beyond what is written, or pad the list with generic skills the posting "
    "does not mention. If a field is not present in the posting, omit it entirely "
    f"rather than guessing. Call the `{_TOOL_NAME}` tool exactly once with the "
    "extracted requirements."
)


def _tool_schema() -> dict:
    return {
        "name": _TOOL_NAME,
        "description": "Record structured requirements extracted from a job posting.",
        "input_schema": JobRequirements.model_json_schema(),
    }


async def analyze_job_posting(
    db: AsyncSession, *, user_id: str | None, title: str, description_text: str
) -> tuple[JobRequirements, AIRequest]:
    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    truncated_text = description_text[:MAX_INPUT_CHARS]

    ai_request = AIRequest(
        user_id=user_id,
        agent_name=AGENT_NAME,
        prompt_version=PROMPT_VERSION,
        model=settings.anthropic_model,
        input_data={"title": title, "description_text": truncated_text, "truncated": len(description_text) > MAX_INPUT_CHARS},
    )
    db.add(ai_request)
    await db.flush()

    validated: JobRequirements | None = None
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
                messages=[
                    {
                        "role": "user",
                        "content": f"Job title: {title}\n\nJob posting:\n\n{truncated_text}",
                    }
                ],
            )
            tool_use_block = next((b for b in message.content if b.type == "tool_use"), None)
            if tool_use_block is None:
                last_error = "Model did not return a tool_use block"
                continue
            validated = JobRequirements.model_validate(tool_use_block.input)
            break
        except ValidationError as exc:
            last_error = str(exc)
            logger.warning("job_analysis_validation_failed", attempt=attempt, error=last_error)
        except Exception as exc:  # noqa: BLE001 - external API failure, must not crash the pipeline
            last_error = str(exc)
            logger.error("job_analysis_call_failed", attempt=attempt, error=last_error)

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
            "AI job analysis failed schema validation after retry", details={"error": last_error}
        )

    return validated, ai_request
