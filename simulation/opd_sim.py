"""SimPy OPD simulation comparing dispatch policies.

Bursty Poisson arrivals, lognormal consults, doctor breaks, urgency mix.
Policies: FCFS, severity-only, MedQueueAI (real priority() and Weights).
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import simpy

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))
from app.queue.priority import Weights, priority  # noqa: E402

LEVEL_MIX = [(1, 0.05), (2, 0.15), (3, 0.25), (4, 0.30), (5, 0.25)]
CONSULT_MEAN = 10.0
CONSULT_SIGMA = 0.5


@dataclass
class SimConfig:
    seed: int = 0
    n_doctors: int = 2
    sim_min: float = 480.0
    base_arrivals_per_hour: float = 10.0
    weights: Weights = field(default_factory=Weights)


@dataclass
class Patient:
    id: int
    level: int
    red_flag: bool
    registered_at: float


def sample_level(rng: np.random.Generator) -> tuple[int, bool]:
    roll = rng.random()
    cumulative = 0.0
    for level, prob in LEVEL_MIX:
        cumulative += prob
        if roll < cumulative:
            return level, level == 1
    return 5, False


def consult_minutes(rng: np.random.Generator) -> float:
    return float(np.clip(rng.lognormal(np.log(CONSULT_MEAN), CONSULT_SIGMA), 2.0, 60.0))


def arrival_rate_per_min(t: float, base_per_min: float) -> float:
    # Bursty: 10-minute surge at 3x every hour.
    return base_per_min * (3.0 if (t % 60.0) < 10.0 else 1.0)


def pick(
    waiting: list[Patient], policy: str, now_min: float, base: datetime, weights: Weights
) -> Patient:
    if policy == "fcfs":
        return min(waiting, key=lambda p: p.registered_at)
    if policy == "severity":
        return min(waiting, key=lambda p: (p.level, p.registered_at))
    if policy == "medqueue":
        now_dt = base.fromtimestamp(base.timestamp() + now_min * 60.0)
        scored = []
        for item in waiting:
            reg = base.fromtimestamp(base.timestamp() + item.registered_at * 60.0)
            scored.append(
                (
                    priority(item.level, reg, now_dt, item.red_flag, weights),
                    item.registered_at,
                    item.id,
                    item,
                )
            )
        scored.sort(key=lambda entry: (-entry[0], entry[1], entry[2]))
        return scored[0][3]
    raise ValueError(f"unknown policy: {policy}")


def run_once(policy: str, config: SimConfig) -> dict:
    rng = np.random.default_rng(config.seed)
    env = simpy.Environment()
    waiting: list[Patient] = []
    waits: dict[int, list[float]] = {level: [] for level, _ in LEVEL_MIX}
    red_waits: list[float] = []
    waits_45: list[float] = []
    busy_min = [0.0 for _ in range(config.n_doctors)]
    base = datetime(2026, 1, 1)
    base_per_min = config.base_arrivals_per_hour / 60.0
    counter = [0]

    def arrival_process():
        t = 0.0
        while t < config.sim_min:
            rate = arrival_rate_per_min(t, base_per_min)
            gap = float(rng.exponential(1.0 / rate))
            t += gap
            if t >= config.sim_min:
                break
            yield env.timeout(gap)
            level, red = sample_level(rng)
            counter[0] += 1
            waiting.append(Patient(counter[0], level, red, env.now))

    def doctor_process(index: int):
        while True:
            if not waiting:
                if env.now >= config.sim_min:
                    return
                yield env.timeout(1.0)
                continue
            patient = pick(waiting, policy, env.now, base, config.weights)
            waiting.remove(patient)
            wait = env.now - patient.registered_at
            waits[patient.level].append(wait)
            if patient.red_flag:
                red_waits.append(wait)
            if patient.level >= 4:
                waits_45.append(wait)
            duration = consult_minutes(rng)
            busy_min[index] += duration
            yield env.timeout(duration)
            if rng.random() < 0.08:
                yield env.timeout(float(rng.uniform(5.0, 15.0)))
            if env.now >= config.sim_min and not waiting:
                return

    env.process(arrival_process())
    for i in range(config.n_doctors):
        env.process(doctor_process(i))
    env.run(until=config.sim_min + 240.0)
    elapsed = float(env.now)

    def p90(values: list[float]) -> float:
        return float(np.percentile(values, 90)) if values else 0.0

    mean_by_level = {
        str(k): round(float(np.mean(v)), 2) if v else 0.0 for k, v in waits.items()
    }
    p90_by_level = {str(k): round(p90(v), 2) for k, v in waits.items()}
    utilisation = round(min(sum(busy_min) / (elapsed * config.n_doctors), 1.0), 3)
    return {
        "policy": policy,
        "seed": config.seed,
        "mean_wait_by_level": mean_by_level,
        "p90_wait_by_level": p90_by_level,
        "red_flag_ttfr_mean": round(float(np.mean(red_waits)), 2) if red_waits else 0.0,
        "utilisation": utilisation,
        "max_wait_45": round(float(max(waits_45)), 2) if waits_45 else 0.0,
        "n_served": sum(len(v) for v in waits.values()),
    }
