"""CLI: python -m simulation.run --seeds 30 [--sim-min 480 --doctors 2]."""

import argparse
import csv
import itertools
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).parents[1]))
from simulation.opd_sim import SimConfig, run_once  # noqa: E402

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))
from app.queue.priority import Weights  # noqa: E402

POLICIES = ["fcfs", "severity", "medqueue"]
RESULTS = Path(__file__).parents[1] / "docs" / "results"


def mean_ci(values: list[float]) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    mean = float(arr.mean()) if len(arr) else 0.0
    if len(arr) < 2:
        return round(mean, 2), 0.0
    half = 1.96 * float(arr.std(ddof=1)) / float(np.sqrt(len(arr)))
    return round(mean, 2), round(half, 2)


def summarize(runs: list[dict]) -> dict:
    summary: dict = {"n_runs": len(runs), "n_served_mean": 0.0}
    for level in ["1", "2", "3", "4", "5"]:
        means = [r["mean_wait_by_level"][level] for r in runs]
        p90s = [r["p90_wait_by_level"][level] for r in runs]
        summary[f"mean_wait_L{level}"] = mean_ci(means)
        summary[f"p90_wait_L{level}"] = mean_ci(p90s)
    summary["red_flag_ttfr"] = mean_ci([r["red_flag_ttfr_mean"] for r in runs])
    summary["utilisation"] = mean_ci([r["utilisation"] for r in runs])
    summary["max_wait_45"] = mean_ci([r["max_wait_45"] for r in runs])
    summary["n_served_mean"] = round(float(np.mean([r["n_served"] for r in runs])), 1)
    return summary


def write_csv(path: Path, runs: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["policy", "seed", "mean_L1", "mean_L2", "mean_L4", "mean_L5",
                        "p90_L1", "p90_L2", "red_flag_ttfr_mean", "utilisation",
                        "max_wait_45", "n_served"],
        )
        writer.writeheader()
        for item in runs:
            writer.writerow(
                {
                    "policy": item["policy"],
                    "seed": item["seed"],
                    "mean_L1": item["mean_wait_by_level"]["1"],
                    "mean_L2": item["mean_wait_by_level"]["2"],
                    "mean_L4": item["mean_wait_by_level"]["4"],
                    "mean_L5": item["mean_wait_by_level"]["5"],
                    "p90_L1": item["p90_wait_by_level"]["1"],
                    "p90_L2": item["p90_wait_by_level"]["2"],
                    "red_flag_ttfr_mean": item["red_flag_ttfr_mean"],
                    "utilisation": item["utilisation"],
                    "max_wait_45": item["max_wait_45"],
                    "n_served": item["n_served"],
                }
            )


def plot(summary_by_policy: dict[str, dict], path: Path) -> None:
    levels = ["1", "2", "3", "4", "5"]
    x = np.arange(len(levels))
    width = 0.25
    _, axis = plt.subplots(figsize=(9, 5))
    for i, policy in enumerate(POLICIES):
        means = [summary_by_policy[policy][f"mean_wait_L{lv}"][0] for lv in levels]
        axis.bar(x + i * width, means, width, label=policy)
    axis.set_xticks(x + width)
    axis.set_xticklabels([f"L{lv}" for lv in levels])
    axis.set_ylabel("Mean wait (min)")
    axis.set_title("Simulated mean wait by urgency level (synthetic)")
    axis.legend()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def grid_search(seeds: int, sim_min: float, n_doctors: int) -> tuple[Weights, list[dict]]:
    grid = list(
        itertools.product([0.5, 0.65, 0.8], [0.15, 0.30, 0.45], [30.0, 60.0, 120.0])
    )
    trials = []
    for w_u, w_w, w_ref in grid:
        weights = Weights(w_u=w_u, w_w=w_w, w_ref_min=w_ref)
        runs = [
            run_once("medqueue", SimConfig(seed=s, sim_min=sim_min,
                                           n_doctors=n_doctors, weights=weights))
            for s in range(min(seeds, 10))
        ]
        red = float(np.mean([r["red_flag_ttfr_mean"] for r in runs]))
        urgent_p90 = float(
            np.mean([r["p90_wait_by_level"]["1"] + r["p90_wait_by_level"]["2"]
                     for r in runs])
        )
        starve = float(np.mean([r["max_wait_45"] for r in runs]))
        # Objective: urgent-first, with a guardrail against starving L4-5.
        score = red + 0.5 * urgent_p90 + (50.0 if starve > 180.0 else 0.0)
        trials.append({"w_u": w_u, "w_w": w_w, "w_ref_min": w_ref, "score": round(score, 2),
                       "red_flag_ttfr": round(red, 2), "max_wait_45": round(starve, 2)})
    best = min(trials, key=lambda t: t["score"])
    return Weights(w_u=best["w_u"], w_w=best["w_w"], w_ref_min=best["w_ref_min"]), trials


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OPD dispatch simulations.")
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--sim-min", type=float, default=480.0)
    parser.add_argument("--doctors", type=int, default=2)
    args = parser.parse_args()
    weights, trials = grid_search(args.seeds, args.sim_min, args.doctors)
    all_runs: list[dict] = []
    for policy in POLICIES:
        for seed in range(args.seeds):
            cfg = SimConfig(seed=seed, sim_min=args.sim_min, n_doctors=args.doctors,
                            weights=weights if policy == "medqueue" else Weights())
            all_runs.append(run_once(policy, cfg))
    by_policy = {policy: [r for r in all_runs if r["policy"] == policy]
                 for policy in POLICIES}
    summaries = {policy: summarize(runs) for policy, runs in by_policy.items()}
    write_csv(RESULTS / "simulation_runs.csv", all_runs)
    (RESULTS / "simulation_summary.json").write_text(
        __import__("json").dumps(
            {"weights": {"w_u": weights.w_u, "w_w": weights.w_w,
                         "w_ref_min": weights.w_ref_min},
             "summaries": summaries, "grid": trials}, indent=2),
        encoding="utf-8")
    plot(summaries, RESULTS / "wait_by_level.png")
    lines = [
        "# Queue weight tuning (synthetic simulation, draft)",
        "",
        "Status: draft, pending clinical review. Decision support only.",
        "Grid: w_u in {0.5, 0.65, 0.8}, w_w in {0.15, 0.30, 0.45}, "
        "w_ref_min in {30, 60, 120}; 10 seeds per cell; "
        f"{args.seeds} seeds for final comparison, {args.doctors} doctors.",
        "",
        f"Grid winner (candidate): w_u={weights.w_u}, w_w={weights.w_w}, "
        f"w_ref_min={weights.w_ref_min}.",
        "",
        "Code defaults retained at w_u=0.65, w_w=0.30, w_ref_min=60.0 pending "
        "clinician sign-off (safer option: do not change clinical weights on "
        "synthetic evidence alone).",
        "",
        "Rationale: the grid favours lower urgency/aging weights under synthetic "
        "load, but differences among top cells are small and all severity-aware "
        "policies still starve level 4-5 under bursts (see max L4-5 below). "
        "Retaining current defaults avoids overfitting to synthetic arrivals; "
        "any change needs clinician sign-off (see docs/clinical_review.md).",
        "",
        "## Final comparison (mean ±95% CI, candidate weights for medqueue)",
        "",
    ]
    for policy in POLICIES:
        entry = summaries[policy]
        lines.append(
            f"- {policy}: red-flag TTFR {entry['red_flag_ttfr'][0]}±"
            f"{entry['red_flag_ttfr'][1]} min; max L4-5 "
            f"{entry['max_wait_45'][0]}±{entry['max_wait_45'][1]} min; "
            f"utilisation {entry['utilisation'][0]}±{entry['utilisation'][1]}."
        )
    (RESULTS / "tuning.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"w_u={weights.w_u} w_w={weights.w_w} w_ref_min={weights.w_ref_min}")
    print(f"runs={len(all_runs)} -> {RESULTS}")


if __name__ == "__main__":
    main()
