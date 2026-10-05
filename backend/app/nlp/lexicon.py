"""Lexicon loading and exact-then-fuzzy matching (draft)."""

import csv
import difflib
from functools import lru_cache
from pathlib import Path

from app.nlp.language import normalise

VOCAB_PATH = Path(__file__).parents[3] / "docs" / "vocabulary.csv"


def _split_synonyms(cell: str) -> list[str]:
    return [part.strip().lower() for part in cell.split(";") if part.strip()]


@lru_cache(maxsize=1)
def load_lexicon(path: str | Path | None = None) -> dict[str, list[str]]:
    """Map canonical symptom to normalised synonym phrases."""
    target = Path(path) if path else VOCAB_PATH
    lexicon: dict[str, list[str]] = {}
    with target.open(encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header: list[str] | None = None
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            if header is None:
                header = [cell.strip() for cell in row]
                continue
            record = dict(zip(header, row, strict=False))
            canonical = (record.get("canonical") or "").strip().lower()
            if not canonical:
                continue
            synonyms = {canonical.replace("_", " "), canonical}
            for column in ("english", "hindi_devanagari", "hindi_romanised",
                           "marathi_devanagari", "marathi_romanised",
                           "code_switched_example"):
                synonyms.update(_split_synonyms(record.get(column, "")))
            lexicon[canonical] = sorted({normalise(item) for item in synonyms if item})
    return lexicon


def match_text(text: str, lexicon: dict[str, list[str]] | None = None) -> list[dict]:
    """Exact substring first, then fuzzy token match; deterministic order."""
    table = lexicon if lexicon is not None else load_lexicon()
    cleaned = normalise(text)
    candidates: list[dict] = []
    for canonical in sorted(table):
        synonyms = table[canonical]
        best: tuple[float, str] | None = None
        for synonym in synonyms:
            if synonym and synonym in cleaned:
                score = 0.95 if len(synonym) >= 4 else 0.75
                if best is None or score > best[0]:
                    best = (score, synonym)
        if best is not None:
            candidates.append(
                {"canonical": canonical, "confidence": best[0],
                 "matched_text": best[1], "method": "exact"}
            )
            continue
        for synonym in synonyms:
            if len(synonym) < 5:
                continue
            for token in set(cleaned.split()):
                if len(token) < 5:
                    continue
                ratio = difflib.SequenceMatcher(None, token, synonym).ratio()
                if ratio >= 0.82 and (best is None or ratio > best[0]):
                    best = (round(ratio, 3), synonym)
        if best is not None:
            candidates.append(
                {"canonical": canonical, "confidence": min(best[0], 0.8),
                 "matched_text": best[1], "method": "fuzzy"}
            )
    candidates.sort(key=lambda item: (-item["confidence"], item["canonical"]))
    return candidates
