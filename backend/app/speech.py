"""Guide speech generation.

Two providers:
- "template": deterministic, offline. Builds speech from approved facts and the designer's key points.
  Used for the offline demo and in tests.
- "anthropic": an LLM rewrites the same material into natural speech. Its output is always passed
  through Fact Guard; on failure it gets one retry with the list of unsupported numbers.
"""
from dataclasses import dataclass

import httpx

from . import factguard
from .config import Settings

ROOM_NAMES = {
    "LIVING": {"ru": "гостиная", "en": "living room"},
    "BEDROOM": {"ru": "спальня", "en": "bedroom"},
    "KITCHEN": {"ru": "кухня", "en": "kitchen"},
    "KITCHEN_HALL": {"ru": "кухня-прихожая", "en": "kitchen and hall"},
    "HALL": {"ru": "прихожая", "en": "hall"},
    "BATH": {"ru": "санузел", "en": "bathroom"},
    "BALCONY": {"ru": "балкон", "en": "balcony"},
}
UNITS = {
    "m2": {"ru": "м²", "en": "m²"},
    "m": {"ru": "м", "en": "m"},
    "cm": {"ru": "см", "en": "cm"},
    "mm": {"ru": "мм", "en": "mm"},
    "K": {"ru": "K", "en": "K"},
}
INTRO = {
    "friendly": {"ru": "Мы в комнате: {room}.", "en": "Here we are in the {room}."},
    "business": {"ru": "Помещение: {room}.", "en": "Room: {room}."},
    "premium": {"ru": "Добро пожаловать: {room}.", "en": "Welcome to the {room}."},
}


@dataclass
class Fact:
    key: str
    room: str | None
    label: dict | None
    value: str | None
    unit: str | None


@dataclass
class Generated:
    text: str
    provider: str
    issues: list[factguard.Issue]


class FactCheckFailed(Exception):
    def __init__(self, text: str, issues: list[factguard.Issue]):
        super().__init__("speech contains numbers that are not in the passport")
        self.text = text
        self.issues = issues


def room_name(room: str, lang: str) -> str:
    return ROOM_NAMES.get(room.upper(), {}).get(lang, room.replace("_", " ").lower())


def format_fact(f: Fact, lang: str) -> str | None:
    if f.value in (None, ""):
        return None
    label = (f.label or {}).get(lang) or f.key.split(".")[-1].replace("_", " ")
    unit = UNITS.get(f.unit or "", {}).get(lang, f.unit or "")
    value = f.value.replace(".", ",") if lang == "ru" else f.value
    return f"{label}: {value}{(' ' + unit) if unit else ''}."


def template_speech(room: str, lang: str, tone: str, facts: list[Fact], key_points: list[str]) -> str:
    parts = [INTRO[tone][lang].format(room=room_name(room, lang))]
    parts += [s for f in facts if (s := format_fact(f, lang))]
    parts += [kp.rstrip(".") + "." for kp in key_points]
    return " ".join(parts)


SYSTEM_PROMPT = """You write short spoken texts for a virtual tour guide of an interior design project.
Rules:
- Write in {language}. 2 to 4 sentences. Tone: {tone}. Speak to the client directly.
- Use ONLY the facts and designer notes given below. Do not invent anything.
- Every number must be written in digits and must be one of the numbers in the facts.
- Do not mention prices, delivery dates, warranties or legal matters.
- Output only the speech text, nothing else."""


def _llm_call(settings: Settings, system: str, user: str) -> str:
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": settings.llm_model,
            "max_tokens": 400,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    return "".join(block.get("text", "") for block in resp.json()["content"]).strip()


def llm_speech(settings: Settings, room: str, lang: str, tone: str, facts: list[Fact], key_points: list[str],
               passport_values: list) -> Generated:
    language = {"ru": "Russian", "en": "English"}.get(lang, lang)
    system = SYSTEM_PROMPT.format(language=language, tone=tone)
    fact_lines = "\n".join(f"- {s}" for f in facts if (s := format_fact(f, "en")))
    notes = "\n".join(f"- {k}" for k in key_points) or "- (none)"
    user = f"Room: {room_name(room, 'en')}\nFacts:\n{fact_lines or '- (none)'}\nDesigner notes:\n{notes}"

    text = _llm_call(settings, system, user)
    issues = factguard.check(text, passport_values)
    if issues:  # one retry with explicit feedback
        bad = ", ".join(i.number for i in issues)
        text = _llm_call(settings, system, user + f"\n\nYour previous answer used numbers not in the facts: {bad}. "
                                                   "Rewrite without them.")
        issues = factguard.check(text, passport_values)
    return Generated(text=text, provider=f"anthropic:{settings.llm_model}", issues=issues)


def generate(settings: Settings, room: str, lang: str, tone: str, facts: list[Fact], key_points: list[str],
             passport_values: list) -> Generated:
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        result = llm_speech(settings, room, lang, tone, facts, key_points, passport_values)
    else:
        text = template_speech(room, lang, tone, facts, key_points)
        result = Generated(text=text, provider="template", issues=factguard.check(text, passport_values))
    if result.issues:
        raise FactCheckFailed(result.text, result.issues)
    return result
