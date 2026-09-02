from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.application_answer_agent import generate_application_answers
from app.core.errors import ExtractionValidationError
from app.db.models import ApplicationAnswer, CandidateProfile, Job, User


async def generate_answers(
    db: AsyncSession, user: User, application_id: str, *, profile: CandidateProfile, job: Job, questions: list[str]
) -> list[ApplicationAnswer]:
    if not questions:
        return []

    try:
        generation, _ = await generate_application_answers(db, user_id=user.id, profile=profile, job=job, questions=questions)
        answers = [
            ApplicationAnswer(
                application_id=application_id,
                question=question,
                answer=result.answer,
                is_grounded=result.is_grounded,
                flag_reason=result.flag_reason,
                reviewed=False,
            )
            for question, result in zip(questions, generation.results, strict=True)
        ]
    except ExtractionValidationError as exc:
        answers = [
            ApplicationAnswer(
                application_id=application_id,
                question=question,
                answer=None,
                is_grounded=False,
                flag_reason=f"AI answer generation failed: {exc}",
                reviewed=False,
            )
            for question in questions
        ]

    db.add_all(answers)
    await db.flush()
    return answers
