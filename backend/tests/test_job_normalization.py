from app.services.job_normalization import content_hash, html_to_text, infer_remote_status, normalize_text


def test_normalize_text_lowercases_and_strips_punctuation():
    assert normalize_text("Senior Software Engineer, Backend!") == "senior software engineer backend"


def test_normalize_text_collapses_whitespace():
    assert normalize_text("  Acme   Corp  ") == "acme corp"


def test_html_to_text_strips_tags():
    html = "<div><h2>About the role</h2><p>Build <b>great</b> things.</p></div>"
    text = html_to_text(html)
    assert "About the role" in text
    assert "Build" in text and "great" in text and "things." in text
    assert "<" not in text


def test_html_to_text_handles_empty_input():
    assert html_to_text("") == ""
    assert html_to_text(None) == ""


def test_html_to_text_handles_html_escaped_markup():
    # Greenhouse returns descriptions as HTML-escaped HTML (entities encoded on
    # top of real markup) rather than plain markup — regression test for a bug
    # caught against live Greenhouse data where a single BeautifulSoup pass only
    # decoded the entities and left the resulting tags as literal visible text.
    escaped = "&lt;div class=&quot;intro&quot;&gt;&lt;p&gt;We build great things.&lt;/p&gt;&lt;/div&gt;"
    text = html_to_text(escaped)
    assert text == "We build great things."
    assert "<" not in text and "&lt;" not in text


def test_infer_remote_status_prefers_explicit_flag():
    assert infer_remote_status("New York, NY", True, "") == "remote"
    assert infer_remote_status("New York, NY", False, "This role is remote-friendly") == "onsite"


def test_infer_remote_status_falls_back_to_keywords():
    assert infer_remote_status("United States", None, "This is a fully remote position.") == "remote"
    assert infer_remote_status("San Francisco", None, "Hybrid role, 3 days in office.") == "hybrid"
    assert infer_remote_status("San Francisco", None, "This is an onsite role.") == "onsite"
    assert infer_remote_status("San Francisco", None, "Great team, great mission.") == "unknown"


def test_content_hash_is_stable_and_sensitive_to_change():
    a = content_hash("Some job description")
    b = content_hash("Some job description")
    c = content_hash("Some other description")
    assert a == b
    assert a != c
