# ML data card — MedQueueAI triage (DRAFT, synthetic-only)

Status: draft, pending clinical review. Decision support only, not diagnosis.
No real patient data is used anywhere in this prototype.

## Source

No public emergency-department triage dataset was accessible without
credentialed access (MIMIC-IV-ED requires credentialing), so all model
results are produced on clearly labelled synthetic data from
`ml/synthetic.py`. Do not claim clinical validity.

## Generator (`ml/synthetic.py`)

- `n` rows (default 6000, seed 42 for train, seed 123 for evaluation).
- Age: mixture — 5% infant (<2), 15% child (2–17), 60% adult (18–64),
  20% older adult (65+); clipped to 0–95.
- Sex: Bernoulli(0.5), optional feature only.
- Symptoms (independent Bernoulli unless noted): chest_pain 0.08,
  chest_tightness 0.06, breathlessness 0.10, fever 0.18, cough 0.20,
  abdominal_pain 0.10, dizziness 0.08, confusion 0.02, unresponsive 0.005,
  seizure 0.008, facial_droop 0.008, slurred_speech 0.01,
  one_sided_weakness 0.01, heavy_bleeding 0.01.
- Vitals (with missingness to exercise missing indicators):
  spo2 ~ Normal(97, 2) clipped 70–100 (8% missing),
  pulse ~ Normal(82, 14) clipped 30–180 (8% missing),
  sbp ~ Normal(122, 18) clipped 60–240 (10% missing),
  dbp ~ Normal(78, 12) clipped 30–140 (15% missing),
  temp_c ~ Normal(37.0, 0.8) clipped 34–42 (8% missing).
  Abnormal tails are enriched conditional on symptoms (e.g. fever raises
  temp_c, chest symptoms lower spo2) to keep plausible correlations.
- Derived: shock_index = pulse / sbp, fever_flag = temp_c >= 38.0,
  hypoxia_flag = spo2 < 94.0, plus one missing indicator per vital.

## Labels (transparent, then noise)

Levels 1–5 mirror `docs/red_flag_rules.yaml` plus plausible urgency tiers:

- 1 if any red-flag pattern (chest + spo2<92, spo2<90, sbp>=200 or <80,
  altered consciousness, stroke signs, heavy bleeding,
  temp>=39 at age <2 or >=75).
- else 2 if temp>=38.5 or pulse>=110 or (chest_pain/breathlessness with
  abnormal vitals).
- else 3 if sbp>=160 or abdominal_pain/dizziness with abnormal vitals.
- else 4 if any mild symptom (fever, cough, abdominal_pain, dizziness).
- else 5 (no symptoms, normal vitals).
- Noise: 10% of rows shift ±1 level (uniform) to avoid a trivially
  separable task. Labels are synthetic and carry no clinical validity.

## Intended use / limits

- Prototype ranking experiments only. Must not guide care.
- Every result trained on synthetic data is labelled as such in
  `ml/MODEL_CARD.md` and `ml/artifacts/metadata.json`.
