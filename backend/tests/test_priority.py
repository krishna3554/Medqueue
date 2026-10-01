from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from app.queue.priority import priority, rank, urgency_weight


@dataclass
class Entry:
    level: int
    registered_at: datetime
    red_flag: bool = False


NOW = datetime(2026, 9, 30, 12, 0)


def test_level_one_outranks_level_five_with_equal_wait() -> None:
    assert priority(1, NOW, NOW, False) > priority(5, NOW, NOW, False)


def test_red_flag_outranks_long_waiting_level_one() -> None:
    flagged = Entry(5, NOW, True)
    long_waiting = Entry(1, NOW - timedelta(hours=12))
    assert rank([long_waiting, flagged], NOW)[0] is flagged


def test_aging_cannot_overtake_fresh_level_one() -> None:
    assert priority(5, NOW - timedelta(minutes=60), NOW, False) == 0.30
    assert priority(5, NOW - timedelta(minutes=60), NOW, False) < priority(1, NOW, NOW, False)


def test_aging_is_capped_at_reference_wait() -> None:
    assert priority(4, NOW - timedelta(minutes=60), NOW, False) == priority(
        4, NOW - timedelta(minutes=600), NOW, False
    )


def test_ties_preserve_first_come_first_served() -> None:
    early = Entry(3, NOW - timedelta(minutes=10))
    late = Entry(3, NOW - timedelta(minutes=10))
    assert rank([late, early], NOW) == [late, early]
    truly_early = Entry(3, NOW - timedelta(minutes=11))
    assert rank([late, truly_early], NOW) == [truly_early, late]


def test_invalid_urgency_level_raises_value_error() -> None:
    with pytest.raises(ValueError, match="1..5"):
        urgency_weight(0)


def test_all_red_flag_queue_uses_remaining_score() -> None:
    urgent = Entry(2, NOW)
    less_urgent = Entry(4, NOW)
    assert rank([less_urgent, urgent], NOW) == [urgent, less_urgent]
