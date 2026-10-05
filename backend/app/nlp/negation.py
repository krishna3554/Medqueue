"""Negation and duration handling for symptom utterances (draft)."""

import re

NEGATIONS = {"no", "not", "without", "denies", "denied", "nahi", "na", "mat", "naka"}
DURATION = re.compile(
    r"(\d+)\s*(day|days|din|divas|week|weeks|hafta|hafte|month|months|mahina|mahine)",
    re.IGNORECASE,
)
HINDI_NUMBERS = {"ek": 1, "do": 2, "teen": 3, "chaar": 4, "paanch": 5,
                 "ekh": 1, "don": 2, "tin": 3, "char": 4, "paach": 5}
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, **HINDI_NUMBERS}


def chunk_spans(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,;]|\\baur\\b|\\band\\b", text) if part.strip()]


def is_negated(chunk: str, matched: str) -> bool:
    lowered = chunk.lower()
    tokens = re.findall(r"[a-z\u0900-\u097F]+", lowered)
    if not tokens:
        return False
    try:
        positions = [i for i, token in enumerate(tokens) if matched.split()[0] in token
                     or token in matched]
        anchor = positions[0] if positions else len(tokens)
    except IndexError:
        anchor = len(tokens)
    window = tokens[max(0, anchor - 3): anchor + 2]
    if set(window) & NEGATIONS:
        return True
    if "nahi" in tokens[anchor: anchor + 2] or "nahin" in tokens[anchor: anchor + 2]:
        return True
    if re.search(r"\bno\s+" + re.escape(matched.split()[0]), lowered):
        return True
    return False


def duration_days(chunk: str) -> int | None:
    match = DURATION.search(chunk.lower())
    if match:
        number, unit = int(match.group(1)), match.group(2).lower()
        if unit.startswith(("week", "haft")):
            return number * 7
        if unit.startswith(("month", "mahin")):
            return number * 30
        return number
    tokens = re.findall(r"[a-z]+", chunk.lower())
    for i, token in enumerate(tokens):
        if token in NUMBER_WORDS and i + 1 < len(tokens):
            nxt = tokens[i + 1]
            if nxt.startswith(("day", "din", "divas")):
                return NUMBER_WORDS[token]
            if nxt.startswith(("week", "haft")):
                return NUMBER_WORDS[token] * 7
            if nxt.startswith(("month", "mahin")):
                return NUMBER_WORDS[token] * 30
    return None


def annotate(text: str, candidates: list[dict]) -> list[dict]:
    chunks = chunk_spans(text.lower())
    annotated = []
    for candidate in candidates:
        matched = candidate["matched_text"]
        owning = next((chunk for chunk in chunks if matched in chunk.lower()), text.lower())
        annotated.append(
            {
                **candidate,
                "negated": is_negated(owning, matched),
                "duration_days": duration_days(owning),
            }
        )
    return annotated
