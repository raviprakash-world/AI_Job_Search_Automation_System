from app.services.text_grounding import find_unsupported_numbers, normalize_number


def test_normalize_number_strips_currency_and_percent_and_commas():
    assert normalize_number("$1,200") == "1200"
    assert normalize_number("45%") == "45"
    assert normalize_number("30") == "30"


def test_find_unsupported_numbers_returns_empty_when_all_present():
    source = "Reduced latency by 30% and saved $1,200 per month"
    generated = "Reduced latency by 30% through caching, saving $1,200 monthly"
    assert find_unsupported_numbers(generated, source) == []


def test_find_unsupported_numbers_flags_new_number():
    source = "Improved reliability across the platform"
    generated = "Improved reliability by 45%"
    assert find_unsupported_numbers(generated, source) == ["45%"]


def test_find_unsupported_numbers_ignores_formatting_differences():
    source = "Saved $1200 in infrastructure costs"
    generated = "Saved $1,200 in infrastructure costs"
    assert find_unsupported_numbers(generated, source) == []


def test_find_unsupported_numbers_empty_source_flags_everything():
    assert find_unsupported_numbers("Cut costs by 20%", "") == ["20%"]
