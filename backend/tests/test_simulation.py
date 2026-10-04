"""Simulation determinism and metric sanity checks."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from simulation.opd_sim import SimConfig, run_once
from simulation.run import mean_ci, summarize


def test_same_seed_is_deterministic() -> None:
    first = run_once("medqueue", SimConfig(seed=7, sim_min=120, n_doctors=2))
    second = run_once("medqueue", SimConfig(seed=7, sim_min=120, n_doctors=2))
    assert first == second


def test_metrics_are_sane() -> None:
    result = run_once("medqueue", SimConfig(seed=1, sim_min=120, n_doctors=2))
    for level in ["1", "2", "3", "4", "5"]:
        assert result["mean_wait_by_level"][level] >= 0
        assert result["p90_wait_by_level"][level] >= result["mean_wait_by_level"][level] - 0.01
    assert 0.0 <= result["utilisation"] <= 1.0
    assert result["red_flag_ttfr_mean"] >= 0
    assert result["max_wait_45"] >= 0
    assert result["n_served"] > 0


def test_mean_ci_and_summarize() -> None:
    assert mean_ci([1.0, 2.0, 3.0])[0] == 2.0
    runs = [run_once("fcfs", SimConfig(seed=s, sim_min=60, n_doctors=1)) for s in range(3)]
    summary = summarize(runs)
    assert summary["n_runs"] == 3
    assert summary["mean_wait_L1"][0] >= 0
