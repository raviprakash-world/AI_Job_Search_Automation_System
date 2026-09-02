import re

_NUMERIC_TOKEN = re.compile(r"\$?\d[\d,]*\.?\d*%?")


def normalize_number(token: str) -> str:
    return token.strip("$%").replace(",", "")


def find_unsupported_numbers(generated_text: str, source_text: str) -> list[str]:
    """Numeric tokens (%, $, counts) present in AI-generated text but not found
    anywhere in the original source text it was supposed to be grounded in.

    Used as a warning heuristic, not a hard block — legitimate paraphrasing of a
    true number is possible (e.g. "half" -> "50%"), so this flags for human
    review rather than silently trusting or silently rejecting the content.
    """
    source_numbers = {normalize_number(m) for m in _NUMERIC_TOKEN.findall(source_text)}
    unsupported = []
    for match in _NUMERIC_TOKEN.findall(generated_text):
        if normalize_number(match) not in source_numbers:
            unsupported.append(match)
    return unsupported
