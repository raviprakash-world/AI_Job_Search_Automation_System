import re
from dataclasses import dataclass
from difflib import SequenceMatcher

CUSTOM_QUESTION_MATCH_THRESHOLD = 0.6

# Types we know how to fill with a plain value. Checkboxes/radios/selects need
# choice-specific handling we don't attempt in this phase — they're reported
# as needing manual input rather than guessed at.
FILLABLE_TEXT_TYPES = {"text", "email", "tel", "textarea"}

_STANDARD_KEYWORDS: dict[str, list[str]] = {
    "first_name": ["first name"],
    "last_name": ["last name"],
    "full_name": ["full name"],
    "email": ["email"],
    "phone": ["phone"],
    "linkedin": ["linkedin"],
}


@dataclass
class DiscoveredField:
    handle: str  # opaque identifier for reporting (id, name, or a synthetic fallback)
    label: str | None
    field_type: str  # text/email/tel/textarea/file/select/checkbox/radio/hidden
    index: int = 0  # position within the page's form-field enumeration, used to locate the live element


@dataclass
class FieldMatch:
    field: DiscoveredField
    target: str | None  # one of _STANDARD_KEYWORDS' keys, "resume", "cover_letter", "custom", or None (unmatched)
    matched_question: str | None = None  # set when target == "custom"


def normalize_label(label: str) -> str:
    first_line = label.splitlines()[0] if label else ""
    stripped = re.sub(r"[*✱]", "", first_line)
    return re.sub(r"\s+", " ", stripped).strip().lower()


def match_standard_field(label: str | None, field_type: str, handle: str = "") -> str | None:
    normalized = normalize_label(label) if label else ""
    handle_lower = handle.lower()

    if field_type == "file":
        # Real Greenhouse forms label the resume upload just "Attach" — the
        # reliable signal is often the field's id/name, not the visible label,
        # so both are checked rather than only falling back when one is empty.
        haystack = f"{normalized} {handle_lower}"
        if "cover" in haystack:
            return "cover_letter"
        return "resume"  # a file upload with no "cover" signal defaults to resume

    if not normalized:
        return None
    if "cover letter" in normalized:
        return "cover_letter"

    for target, keywords in _STANDARD_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return target
    return None


def match_custom_question(label: str | None, candidate_questions: list[str]) -> str | None:
    if not label or not candidate_questions:
        return None
    normalized_label = normalize_label(label)

    best_question = None
    best_ratio = 0.0
    for question in candidate_questions:
        ratio = SequenceMatcher(None, normalized_label, question.strip().lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_question = question

    return best_question if best_ratio >= CUSTOM_QUESTION_MATCH_THRESHOLD else None


def match_fields(fields: list[DiscoveredField], candidate_questions: list[str]) -> list[FieldMatch]:
    """Matches discovered form fields to known targets or custom answers.

    Deliberately conservative: hidden fields are never surfaced (the user
    can't act on them), non-text field types (checkbox/radio/select) are never
    guessed at even if a label matches, and anything left unmatched is
    reported for manual input rather than silently skipped or invented.
    """
    remaining_questions = list(candidate_questions)
    matches: list[FieldMatch] = []

    for field in fields:
        if field.field_type == "hidden":
            continue

        if field.field_type == "file":
            target = match_standard_field(field.label, field.field_type, handle=field.handle)
            matches.append(FieldMatch(field=field, target=target))
            continue

        if field.field_type not in FILLABLE_TEXT_TYPES:
            matches.append(FieldMatch(field=field, target=None))
            continue

        standard_target = match_standard_field(field.label, field.field_type, handle=field.handle)
        if standard_target:
            matches.append(FieldMatch(field=field, target=standard_target))
            continue

        matched_question = match_custom_question(field.label, remaining_questions)
        if matched_question:
            remaining_questions.remove(matched_question)
            matches.append(FieldMatch(field=field, target="custom", matched_question=matched_question))
            continue

        matches.append(FieldMatch(field=field, target=None))

    return matches
