"""Fact Guard: every number in the guide's speech must come from the approved passport.

The check runs after generation (post-generation verification). A spoken number
is supported when it equals a passport value, or equals it rounded to the number
of decimals the speech uses ("2,9 m" is supported by a passport value 2.89).
Any other number is reported as unsupported, and the speech is rejected.

Known limitation: numbers written as words ("два", "three") are not detected;
the LLM prompt therefore asks for digits only.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
import re

# "2 700", "2700", "2,89", "2.89", "12" -- thousands with a (narrow) space first.
_NUM = r"\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_UNIT = (
    r"м²|м2|кв\.?\s?м|m²|m2|sq\.?\s?m|мм|mm|см|cm|м|m|K|К|°C|°|%|"
    r"лм|lm|этаж\w*|floor\w*|комнат\w*|room\w*"
)
NUMBER_RE = re.compile(
    rf"(?<![\w.,])(?P<num>{_NUM})(?:-?(?:th|st|nd|rd|м|й|го|ом|ем))?\s*(?P<unit>{_UNIT})?(?!\w)",
    re.IGNORECASE,
)


@dataclass
class Issue:
    number: str
    unit: str | None
    context: str


def _to_decimal(raw: str) -> Decimal | None:
    cleaned = re.sub(r"[   ]", "", raw).replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def extract_numbers(text: str) -> list[tuple[Decimal, str, str | None, str]]:
    """Return (value, raw, unit, context) for every number in the text."""
    found = []
    for m in NUMBER_RE.finditer(text):
        value = _to_decimal(m.group("num"))
        if value is None:
            continue
        start, end = max(m.start() - 30, 0), min(m.end() + 30, len(text))
        found.append((value, m.group("num"), m.group("unit"), text[start:end].strip()))
    return found


def allowed_values(passport_values: list[str | float | int | None]) -> set[Decimal]:
    """All numbers that appear in approved passport values."""
    allowed: set[Decimal] = set()
    for v in passport_values:
        if v is None:
            continue
        for value, *_ in extract_numbers(str(v)):
            allowed.add(value)
    return allowed


def _decimals(raw: str) -> int:
    raw = raw.replace(",", ".")
    return len(raw.split(".")[1]) if "." in raw else 0


def is_supported(value: Decimal, raw: str, allowed: set[Decimal]) -> bool:
    if value in allowed:
        return True
    places = Decimal(1).scaleb(-_decimals(raw))  # 1, 0.1, 0.01 ...
    return any(a.quantize(places, rounding=ROUND_HALF_UP) == value for a in allowed)


def check(text: str, passport_values: list[str | float | int | None]) -> list[Issue]:
    """Return the list of unsupported numbers; an empty list means the text passes."""
    allowed = allowed_values(passport_values)
    issues = []
    for value, raw, unit, context in extract_numbers(text):
        if not is_supported(value, raw, allowed):
            issues.append(Issue(number=raw, unit=unit, context=context))
    return issues
