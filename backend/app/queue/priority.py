"""Pure functions for transparent, deterministic queue ordering."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Weights:
    """Draft engineering weights; these require clinical review before use."""

    w_u: float = 0.65
    w_w: float = 0.30
    w_f: float = 1.0
    w_ref_min: float = 60.0


DEFAULT_WEIGHTS = Weights()


class QueueEntry(Protocol):
    level: int
    registered_at: datetime
    red_flag: bool


def urgency_weight(level: int) -> float:
    """Map urgency level 1..5 to a normalized severity score 1.0..0.0."""
    if not 1 <= level <= 5:
        raise ValueError(f"urgency level must be 1..5, got {level}")
    return (5 - level) / 4


def priority(
    level: int,
    registered_at: datetime,
    now: datetime,
    red_flag: bool,
    w: Weights = DEFAULT_WEIGHTS,
) -> float:
    """Return the draft priority score, including capped waiting-time aging."""
    if w.w_ref_min <= 0:
        raise ValueError("w_ref_min must be greater than zero")
    wait_min = max((now - registered_at).total_seconds() / 60, 0)
    aging = min(wait_min / w.w_ref_min, 1.0)
    return w.w_u * urgency_weight(level) + w.w_w * aging + (w.w_f if red_flag else 0.0)


def rank(
    entries: Sequence[QueueEntry], now: datetime, w: Weights = DEFAULT_WEIGHTS
) -> list[QueueEntry]:
    """Sort by descending priority, breaking ties by earlier registration (FCFS)."""
    return sorted(
        entries,
        key=lambda entry: (
            -priority(entry.level, entry.registered_at, now, entry.red_flag, w),
            entry.registered_at,
        ),
    )
