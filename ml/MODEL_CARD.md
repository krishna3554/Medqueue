# ML model card — MedQueueAI urgency model (DRAFT, synthetic-only)

Status: draft, pending clinical review. Decision support only, not diagnosis.
All metrics below are on synthetic data and must not be interpreted as
clinical validity.

## Model

- Candidates: LogisticRegression (baseline), RandomForest, XGBoost,
  stratified split, class weights balanced, probabilities calibrated
  (sigmoid, cv=3).
- Features: symptom flags, age band, sex (optional), spo2, pulse, sbp, dbp,
  temp_c, shock_index (pulse/sbp), fever_flag, hypoxia_flag, plus
  missing-value indicators. Imputation uses training medians.
- Selection: highest recall on levels 1–2 first, then interpretability
  (LogisticRegression > RandomForest > XGBoost).
- Rules-first precedence is enforced at serving time: any matching
  red-flag rule overrides the model. Model failure falls back to
  rules + stub and surfaces an "AI unavailable" state. Registration is
  never blocked by the model.

## Artifacts

- `ml/artifacts/model.joblib`, `medians.joblib`, `features.joblib`,
  `metadata.json` (only `metadata.json` is committed; all binaries are
  gitignored). `model_version` is stored on each visit at triage time.
- See `ml/artifacts/metadata.json` for the selected model, version,
  test metrics, and the `synthetic_only: true` flag.

## Metrics (synthetic test set, seed 123)

Reported by `ml/evaluate.py`: AUC (one-vs-rest), per-class recall
(levels 1–2 highlighted), Cohen's kappa, within-±1-level accuracy,
calibration curve data, and subgroup recall by age band. See
`docs/results/model_evaluation.md` for the latest numbers.

## Limitations

- Trained and evaluated on synthetic data only; distributions are
  engineered, not epidemiological.
- Missingness is simulated, not chart-abstracted.
- Explanations are SHAP top-3 feature contributions for the predicted
  class (or a deterministic deviation fallback when SHAP is unavailable);
  they are rationales for debugging, not clinical reasons.
- Requires clinician sign-off on every rule, weight, threshold, and
  deployment decision listed in `docs/clinical_review.md`.
