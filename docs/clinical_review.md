# Clinical review checklist (draft — sign-off required)

Status: draft. Nothing below is clinically validated. Every item needs
explicit clinician sign-off before any non-prototype use. This is decision
support, not diagnosis.

## Red-flag rules (`docs/red_flag_rules.yaml`, version 0.1)

| ID | Name | Needs review |
|----|------|--------------|
| RF01 | Chest symptoms with low oxygen (chest pain/tightness + spo2 < 92) | threshold 92, symptom set |
| RF02 | Chest pain with breathlessness | symptom pairing |
| RF03 | Severe hypoxia (spo2 < 90) | threshold 90 |
| RF04 | Extreme blood pressure (sbp ≥ 200 or < 80) | both thresholds |
| RF05 | Altered consciousness (confusion, unresponsive, seizure) | symptom set |
| RF06 | Stroke signs (facial droop, slurred speech, one-sided weakness) | symptom set |
| RF07 | Severe bleeding (heavy_bleeding) | definition of severe |
| RF08 | High fever at age extremes (temp ≥ 39.0 and age < 2 or ≥ 75) | temp and age cutoffs |

Also review: missing vitals are treated as unknown (never normal);
`evaluate_rules` semantics (`all`/`any`, comparisons, `or`); the rules file
versioning and change process.

## Queue weights (`backend/app/queue/priority.py`)

- `w_u = 0.65` (urgency weight), `w_w = 0.30` (waiting-time weight),
  `w_f = 1.0` (red-flag boost), `w_ref_min = 60.0` (aging reference).
- Grid winner on synthetic data was (0.5, 0.15, 60.0); code defaults were
  deliberately retained pending sign-off (see `docs/results/tuning.md`).
- Review: urgency mapping (levels 1–5 → 1.0–0.0), aging cap at `w_ref_min`,
  red-flag boost magnitude, tie-break by registration time, override
  semantics (override replaces base level; red-flag and aging still apply).

## Wait estimates (`backend/app/queue/wait.py`, `consultation_estimates`)

- Per-doctor rolling mean (last 20 consults, minimum 3 samples) with
  `avg_consult_min` and department-mean fallbacks; unassigned visits pool
  work ahead across available doctors; no remaining-time tracking for
  in-review visits. Review defaults (`avg_consult_min = 10.0`,
  `DEPT_DEFAULT_MIN = 10.0`) and the 0–240 minute duration guard.

## Triage model (`ml/`, synthetic-only)

- Features, medians imputation, calibration, selection by levels 1–2
  recall; XGBoost selected on synthetic data (`synthetic-v0.1`).
- SHAP top-3 explanations (or deterministic fallback) and one-sentence
  rationale; `model_version` stored per visit; rules always override the
  model; model failure falls back to stub with "AI unavailable".
- No clinical validity is claimed; see `ml/MODEL_CARD.md`,
  `ml/DATA_CARD.md`, `docs/results/model_evaluation.md`.

## Symptom NLP (`backend/app/nlp/`, `docs/vocabulary.csv`)

- 150-canonical draft lexicon (Devanagari + Romanised Hindi/Marathi,
  code-switched phrases); exact-then-fuzzy matching, negation
  ("no fever", "bukhar nahi") and duration ("3 days") handling.
- Marked "draft, needs native-speaker review"; extraction never saves —
  `POST /visits/{id}/symptoms` saves only after human confirmation.

## Simulation (`simulation/`, `docs/results/`)

- Bursty arrivals, lognormal consults, breaks, urgency mix; FCFS vs
  severity-only vs MedQueueAI; 30 seeds with mean ±95% CI. Synthetic
  evidence only; starvation of level 4–5 under bursts is a known
  trade-off requiring capacity planning, not just weights.
