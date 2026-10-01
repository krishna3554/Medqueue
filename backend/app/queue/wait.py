"""Consultation-duration aggregation and wait estimation utilities."""

from collections import defaultdict, deque
from typing import Protocol


class DoctorQueueEntry(Protocol):
    doctor_id: str | None


class RollingMean:
    """Fixed-size rolling consultation means with a minimum-sample fallback."""

    def __init__(self, n: int = 20, min_samples: int = 3) -> None:
        if n < 1:
            raise ValueError("n must be at least 1")
        if min_samples < 1:
            raise ValueError("min_samples must be at least 1")
        self.n = n
        self.min_samples = min_samples
        self._samples: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=n))
        self._department_samples: deque[float] = deque(maxlen=n)

    def add(self, doctor_id: str, consultation_min: float) -> None:
        if consultation_min < 0:
            raise ValueError("consultation duration cannot be negative")
        self._samples[doctor_id].append(consultation_min)
        self._department_samples.append(consultation_min)

    @staticmethod
    def _mean(samples: deque[float]) -> float:
        return sum(samples) / len(samples)

    def for_doctor(self, doctor_id: str, dept_default: float) -> float:
        samples = self._samples[doctor_id]
        if len(samples) >= self.min_samples:
            return self._mean(samples)
        if self._department_samples:
            return self._mean(self._department_samples)
        return dept_default


def estimate_wait_min(
    position_ahead: list[DoctorQueueEntry],
    avg_consult_min: dict[str | None, float],
    dept_default: float,
    current_remaining_min: float = 0.0,
) -> float:
    """Estimate wait from work ahead, using doctor-specific duration estimates."""
    total = current_remaining_min
    for entry in position_ahead:
        total += avg_consult_min.get(entry.doctor_id, dept_default)
    return round(total, 1)
