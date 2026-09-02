from abc import ABC

from pydantic import BaseModel, Field


class CustomAnswer(BaseModel):
    question: str
    answer: str


class FillContext(BaseModel):
    """Everything an adapter needs to fill a real application form.

    Only grounded, user-reviewed answers ever reach here — that filtering
    happens in the calling service, not the adapter.
    """

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    links: dict[str, str] = Field(default_factory=dict)
    resume_file_path: str | None = None
    cover_letter_file_path: str | None = None
    cover_letter_text: str | None = None  # used when the form has a text-area cover letter field instead of an upload
    custom_answers: list[CustomAnswer] = Field(default_factory=list)


class FillResult(BaseModel):
    success: bool
    fields_filled: list[str] = Field(default_factory=list)
    fields_needing_manual_input: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None


class ApplicationAdapter(ABC):
    """Template method: navigate -> check blocking -> discover fields -> match
    -> fill -> check blocking again. Subclasses only resolve the actual apply
    URL, since that's the one thing that differs between platforms (Greenhouse
    hosts the form at the posting URL itself; Lever hosts it at `{url}/apply`).
    """

    name: str

    def resolve_apply_url(self, posting_url: str) -> str:
        return posting_url

    async def fill_application(self, page, apply_url: str, context: FillContext) -> FillResult:
        # Deferred imports: filling.py imports FillContext/FillResult from this
        # module, so importing it back at module load time would be circular.
        from app.browser_automation.blocking_detection import detect_blocking_condition
        from app.browser_automation.field_discovery import discover_fields, to_discovered_fields
        from app.browser_automation.field_matching import match_fields
        from app.browser_automation.filling import fill_matched_fields

        try:
            await page.goto(self.resolve_apply_url(apply_url), wait_until="domcontentloaded", timeout=30_000)
        except Exception as exc:  # noqa: BLE001 - a navigation failure is a blocked state, not a crash
            return FillResult(success=False, blocked_reason=f"Could not load the application page: {exc}")

        blocked = await detect_blocking_condition(page)
        if blocked:
            return FillResult(success=False, blocked_reason=blocked)

        raw_fields = await discover_fields(page)
        if not raw_fields:
            return FillResult(success=False, blocked_reason="No application form found on this page")

        fields = to_discovered_fields(raw_fields)
        questions = [a.question for a in context.custom_answers]
        matches = match_fields(fields, questions)
        result = await fill_matched_fields(page, matches, context)

        blocked_after = await detect_blocking_condition(page)
        if blocked_after:
            result.success = False
            result.blocked_reason = blocked_after

        return result
