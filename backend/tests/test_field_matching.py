from app.browser_automation.field_matching import (
    DiscoveredField,
    match_custom_question,
    match_fields,
    match_standard_field,
    normalize_label,
)


def test_normalize_label_strips_required_marker_and_extra_lines():
    assert normalize_label("First Name*") == "first name"
    assert normalize_label("Email\n✱\nrequired") == "email"
    assert normalize_label("  Phone   Number  ") == "phone number"


def test_match_standard_field_by_label():
    assert match_standard_field("First Name*", "text") == "first_name"
    assert match_standard_field("Last Name*", "text") == "last_name"
    assert match_standard_field("Full name", "text") == "full_name"
    assert match_standard_field("Email*", "email") == "email"
    assert match_standard_field("Phone*", "tel") == "phone"
    assert match_standard_field("LinkedIn URL", "text") == "linkedin"


def test_match_standard_field_file_upload_defaults_to_resume_on_generic_label():
    # Real Greenhouse forms label the resume upload just "Attach" — the id is
    # the reliable signal there, not the label text.
    assert match_standard_field("Attach", "file", handle="resume") == "resume"


def test_match_standard_field_file_upload_detects_cover_letter():
    assert match_standard_field("Attach", "file", handle="cover_letter") == "cover_letter"
    assert match_standard_field("Cover Letter", "file") == "cover_letter"


def test_match_standard_field_unrelated_label_is_unmatched():
    assert match_standard_field("Gender", "select") is None
    assert match_standard_field("Current company", "text") is None


def test_match_custom_question_finds_close_paraphrase():
    questions = ["Are you authorized to work in the country for which you applied?"]
    result = match_custom_question("Are you authorized to work in the country you applied to?", questions)
    assert result == questions[0]


def test_match_custom_question_returns_none_below_threshold():
    questions = ["What is your expected compensation range?"]
    assert match_custom_question("Do you have a valid driver's license?", questions) is None


def test_match_custom_question_returns_none_without_label_or_questions():
    assert match_custom_question(None, ["some question"]) is None
    assert match_custom_question("A label", []) is None


# --- match_fields (the full pipeline) ------------------------------------------


def test_match_fields_skips_hidden_fields_entirely():
    fields = [DiscoveredField(handle="csrf", label=None, field_type="hidden", index=0)]
    matches = match_fields(fields, [])
    assert matches == []


def test_match_fields_never_guesses_on_checkbox_radio_or_select():
    fields = [
        DiscoveredField(handle="gender", label="Gender", field_type="select", index=0),
        DiscoveredField(handle="pronouns", label="He/him", field_type="checkbox", index=1),
    ]
    matches = match_fields(fields, [])
    assert all(m.target is None for m in matches)


def test_match_fields_matches_standard_then_falls_back_to_custom_question():
    fields = [
        DiscoveredField(handle="email", label="Email*", field_type="email", index=0),
        DiscoveredField(
            handle="question_1",
            label="Are you authorized to work in the country for which you applied? *",
            field_type="text",
            index=1,
        ),
        DiscoveredField(handle="question_2", label="Completely unrelated question about hobbies", field_type="text", index=2),
    ]
    questions = ["Are you authorized to work in the country you applied to?"]
    matches = match_fields(fields, questions)

    assert matches[0].target == "email"
    assert matches[1].target == "custom"
    assert matches[1].matched_question == questions[0]
    assert matches[2].target is None  # genuinely unmatched, not guessed


def test_match_fields_does_not_reuse_the_same_custom_question_twice():
    fields = [
        DiscoveredField(handle="q1", label="Why do you want to join Figma?", field_type="textarea", index=0),
        DiscoveredField(handle="q2", label="Why do you want to join Figma?", field_type="textarea", index=1),
    ]
    questions = ["Why do you want to join Figma?"]
    matches = match_fields(fields, questions)

    matched = [m for m in matches if m.target == "custom"]
    assert len(matched) == 1  # the second identical field can't reuse the same answer
