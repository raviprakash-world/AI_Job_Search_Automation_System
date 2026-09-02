from sqlalchemy.ext.asyncio import AsyncSession

from app.browser_automation.base import CustomAnswer, FillContext, FillResult
from app.browser_automation.registry import detect_provider, get_adapter
from app.browser_automation.session import browser_page
from app.core.config import get_settings
from app.core.errors import ConflictError
from app.db.models import Application, User
from app.services import application_service, profile_service

_STAGEABLE_STATUSES = {"approved", "submission_blocked"}


def _screenshot_path(application_id: str):
    settings = get_settings()
    path = settings.resume_storage_path.parent / "staging_screenshots" / f"{application_id}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _build_context(application: Application, profile, user: User) -> FillContext:
    resume_version = application.resume_version
    cover_letter_version = application.cover_letter_version

    # Only answers the user has vetted — grounded by the AI or explicitly
    # reviewed/edited — are ever typed into the real form. A still-flagged,
    # unreviewed answer is left for the user to fill in themselves.
    reviewed_answers = [
        CustomAnswer(question=a.question, answer=a.answer)
        for a in application.answers
        if a.answer and (a.is_grounded or a.reviewed)
    ]

    return FillContext(
        full_name=profile.full_name,
        email=user.email,
        phone=profile.phone,
        links=profile.links or {},
        resume_file_path=resume_version.file_path if resume_version else None,
        cover_letter_file_path=cover_letter_version.file_path if cover_letter_version else None,
        cover_letter_text=cover_letter_version.body_text if cover_letter_version else None,
        custom_answers=reviewed_answers,
    )


async def stage_application(db: AsyncSession, user: User, application_id: str) -> Application:
    application = await application_service.get_owned_application(db, user.id, application_id)
    if application.status not in _STAGEABLE_STATUSES:
        raise ConflictError(f"Cannot stage an application in status '{application.status}' — approve it first")

    job = application.job
    provider = detect_provider(job.posting_url or "")
    adapter = get_adapter(provider) if provider else None

    if adapter is None or not job.posting_url:
        result = FillResult(
            success=False,
            blocked_reason="No automation adapter available for this job board — please apply manually",
        )
    else:
        profile = await profile_service.get_profile_by_user(db, user.id)
        context = _build_context(application, profile, user)
        try:
            async with browser_page() as page:
                result = await adapter.fill_application(page, job.posting_url, context)
                await _save_screenshot(page, application)
        except Exception as exc:  # noqa: BLE001 - staging must never crash the request, only report a blocked state
            result = FillResult(success=False, blocked_reason=f"Unexpected error while staging: {exc}")

    application.staging_notes = {
        "fields_filled": result.fields_filled,
        "fields_needing_manual_input": result.fields_needing_manual_input,
        "blocked_reason": result.blocked_reason,
    }

    new_status = "staged" if result.success else "submission_blocked"
    application_service.record_transition(db, application, new_status, actor="system", note=result.blocked_reason)
    await db.commit()
    return await application_service.get_owned_application(db, user.id, application_id)


async def _save_screenshot(page, application: Application) -> None:
    try:
        path = _screenshot_path(application.id)
        await page.screenshot(path=str(path), full_page=True)
        application.staged_screenshot_path = str(path)
    except Exception:  # noqa: BLE001 - a screenshot failure shouldn't hide a successful fill result
        pass
