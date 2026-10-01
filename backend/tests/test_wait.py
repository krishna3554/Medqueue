from dataclasses import dataclass

from app.queue.wait import RollingMean, estimate_wait_min


@dataclass
class Entry:
    doctor_id: str | None


def test_estimates_wait_with_doctor_and_department_values() -> None:
    assert estimate_wait_min([Entry("a"), Entry("missing")], {"a": 8.5}, 12, 3) == 23.5


def test_rolling_mean_uses_department_until_doctor_has_three_samples() -> None:
    rolling = RollingMean()
    rolling.add("a", 10)
    rolling.add("b", 20)
    assert rolling.for_doctor("a", 15) == 15
    rolling.add("a", 30)
    rolling.add("a", 20)
    assert rolling.for_doctor("a", 15) == 20
