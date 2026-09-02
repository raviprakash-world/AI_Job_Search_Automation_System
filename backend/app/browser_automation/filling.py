from app.browser_automation.base import FillContext, FillResult
from app.browser_automation.field_matching import FieldMatch


def _field_display_name(match: FieldMatch) -> str:
    return match.field.label or match.field.handle


async def fill_matched_fields(page, matches: list[FieldMatch], context: FillContext) -> FillResult:
    """Applies each match to the live page. Never touches a field with no
    match — those are reported for the user to fill in themselves."""
    form_fields = page.locator("form").locator("input, textarea, select")

    fields_filled: list[str] = []
    fields_needing_manual_input: list[str] = []
    answers_by_question = {a.question: a.answer for a in context.custom_answers}

    for match in matches:
        display_name = _field_display_name(match)
        locator = form_fields.nth(match.field.index)

        if match.target is None:
            fields_needing_manual_input.append(display_name)
            continue

        try:
            filled = await _fill_one(locator, match, context, answers_by_question)
        except Exception:  # noqa: BLE001 - a single field failing to fill must not abort the whole form
            filled = False

        if filled:
            fields_filled.append(display_name)
        else:
            fields_needing_manual_input.append(display_name)

    return FillResult(success=True, fields_filled=fields_filled, fields_needing_manual_input=fields_needing_manual_input)


async def _fill_one(locator, match: FieldMatch, context: FillContext, answers_by_question: dict[str, str]) -> bool:
    target = match.target
    field_type = match.field.field_type

    if target == "resume":
        if not context.resume_file_path:
            return False
        await locator.set_input_files(context.resume_file_path)
        return True

    if target == "cover_letter":
        if field_type == "file":
            if not context.cover_letter_file_path:
                return False
            await locator.set_input_files(context.cover_letter_file_path)
            return True
        if not context.cover_letter_text:
            return False
        await locator.fill(context.cover_letter_text)
        return True

    if target == "custom":
        answer = answers_by_question.get(match.matched_question or "")
        if not answer:
            return False
        await locator.fill(answer)
        return True

    value = _standard_value(target, context)
    if not value:
        return False
    await locator.fill(value)
    return True


def _standard_value(target: str, context: FillContext) -> str | None:
    if target == "email":
        return context.email
    if target == "phone":
        return context.phone
    if target == "full_name":
        return context.full_name
    if target == "first_name":
        return context.full_name.split(" ", 1)[0] if context.full_name else None
    if target == "last_name":
        if context.full_name and " " in context.full_name:
            return context.full_name.split(" ", 1)[1]
        return None
    if target == "linkedin":
        return context.links.get("linkedin") or context.links.get("LinkedIn")
    return None
