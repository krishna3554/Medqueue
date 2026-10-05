# Queue weight tuning (synthetic simulation, draft)

Status: draft, pending clinical review. Decision support only.
Grid: w_u in {0.5, 0.65, 0.8}, w_w in {0.15, 0.30, 0.45}, w_ref_min in {30, 60, 120}; 10 seeds per cell; 30 seeds for final comparison, 2 doctors.

Grid winner (candidate): w_u=0.5, w_w=0.15, w_ref_min=60.0.

Code defaults retained at w_u=0.65, w_w=0.30, w_ref_min=60.0 pending clinician sign-off (safer option: do not change clinical weights on synthetic evidence alone).

Rationale: the grid favours lower urgency/aging weights under synthetic load, but differences among top cells are small and all severity-aware policies still starve level 4-5 under bursts (see max L4-5 below). Retaining current defaults avoids overfitting to synthetic arrivals; any change needs clinician sign-off (see docs/clinical_review.md).

## Final comparison (mean ±95% CI, candidate weights for medqueue)

- fcfs: red-flag TTFR 58.18±16.49 min; max L4-5 120.78±21.04 min; utilisation 0.76±0.03.
- severity: red-flag TTFR 3.83±0.75 min; max L4-5 293.91±46.69 min; utilisation 0.76±0.03.
- medqueue: red-flag TTFR 3.83±0.75 min; max L4-5 284.58±47.47 min; utilisation 0.76±0.03.
