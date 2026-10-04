"""Language detection and Romanised normalisation (draft heuristics)."""

import re

DEVANAGARI = re.compile(r"[\u0900-\u097F]")
HINDI_HINTS = {"hai", "hain", "mein", "nahi", "bukhar", "khansi", "dard", "saans",
               "ulti", "dast", "chakkar", "gala", "naak", "bhookh", "neend"}
MARATHI_HINTS = {"aahe", "nahi", "mala", "dukhan", "dukhane", "lagne", "yene",
                 "khokla", "potdukhi", "dokedukhi", "taap", "zhop", "gham"}


def detect_language(text: str) -> str:
    lowered = text.lower()
    if DEVANAGARI.search(text):
        words = set(re.findall(r"[\u0900-\u097F]+", text))
        marathi_markers = {"आहे", "मला", "झोप", "खोकला", "पोट", "डोके", "ताप", "घाम"}
        if words & marathi_markers:
            return "mr"
        return "hi"
    tokens = set(re.findall(r"[a-z]+", lowered))
    if tokens & MARATHI_HINTS:
        return "mr"
    if tokens & HINDI_HINTS:
        return "hi"
    if re.search(r"[a-z]", lowered):
        return "en"
    return "unknown"


def normalise(text: str) -> str:
    lowered = text.lower().strip()
    lowered = re.sub(r"\s+", " ", lowered)
    # Collapse repeated letters in Romanised text (bukhaar -> bukhar).
    lowered = re.sub(r"([a-z])\1+", r"\1", lowered)
    replacements = {
        "w": "v",
        "khansi": "khansi",
        "bhukhar": "bukhar",
        "bokhar": "bukhar",
        "dardh": "dard",
        "sans": "saans",
    }
    for src, dst in replacements.items():
        lowered = re.sub(rf"\b{src}\b", dst, lowered)
    return lowered
