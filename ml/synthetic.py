"""Clearly synthetic ED-triage generator for prototype experiments only.

No real patient data. Distributions are clinically plausible by construction
but carry no epidemiological validity. See ml/DATA_CARD.md.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

SYMPTOMS = [
    "chest_pain",
    "chest_tightness",
    "breathlessness",
    "fever",
    "cough",
    "abdominal_pain",
    "dizziness",
    "confusion",
    "unresponsive",
    "seizure",
    "facial_droop",
    "slurred_speech",
    "one_sided_weakness",
    "heavy_bleeding",
]

VITALS = ["spo2", "pulse", "sbp", "dbp", "temp_c"]

SYMPTOM_PROBS = {
    "chest_pain": 0.08,
    "chest_tightness": 0.06,
    "breathlessness": 0.10,
    "fever": 0.18,
    "cough": 0.20,
    "abdominal_pain": 0.10,
    "dizziness": 0.08,
    "confusion": 0.02,
    "unresponsive": 0.005,
    "seizure": 0.008,
    "facial_droop": 0.008,
    "slurred_speech": 0.01,
    "one_sided_weakness": 0.01,
    "heavy_bleeding": 0.01,
}

MISSING_PROBS = {"spo2": 0.08, "pulse": 0.08, "sbp": 0.10, "dbp": 0.15, "temp_c": 0.08}

FEATURE_COLUMNS = (
    [f"sym_{name}" for name in SYMPTOMS]
    + ["age", "age_band", "sex"]
    + VITALS
    + ["shock_index", "fever_flag", "hypoxia_flag"]
    + [f"{ vital }_missing" for vital in VITALS]
)


@dataclass(frozen=True)
class SyntheticConfig:
    n: int = 6000
    seed: int = 42
    noise_rate: float = 0.10


def age_band(age: float) -> int:
    if age < 2:
        return 0
    if age < 18:
        return 1
    if age < 65:
        return 2
    return 3


def transparent_level(row: dict) -> int:
    symptoms = {name for name in SYMPTOMS if row.get(f"sym_{name}", 0) == 1}
    spo2 = row.get("spo2")
    pulse = row.get("pulse")
    sbp = row.get("sbp")
    temp = row.get("temp_c")
    age = row.get("age", 30)
    chest = bool({"chest_pain", "chest_tightness"} & symptoms)
    altered = bool({"confusion", "unresponsive", "seizure"} & symptoms)
    stroke = bool({"facial_droop", "slurred_speech", "one_sided_weakness"} & symptoms)
    if (
        (chest and spo2 is not None and spo2 < 92)
        or (chest and "breathlessness" in symptoms)
        or (spo2 is not None and spo2 < 90)
        or (sbp is not None and (sbp >= 200 or sbp < 80))
        or altered
        or stroke
        or "heavy_bleeding" in symptoms
        or (temp is not None and temp >= 39.0 and (age < 2 or age >= 75))
    ):
        return 1
    if (
        (temp is not None and temp >= 38.5)
        or (pulse is not None and pulse >= 110)
        or (bool({"chest_pain", "breathlessness"} & symptoms))
    ):
        return 2
    if (sbp is not None and sbp >= 160) or bool(
        {"abdominal_pain", "dizziness"} & symptoms
    ):
        return 3
    if bool({"fever", "cough", "abdominal_pain", "dizziness"} & symptoms):
        return 4
    return 5


def generate(config: SyntheticConfig = SyntheticConfig()) -> pd.DataFrame:
    rng = np.random.default_rng(config.seed)
    n = config.n
    ages = np.concatenate(
        [
            rng.uniform(0, 2, size=int(n * 0.05)),
            rng.uniform(2, 18, size=int(n * 0.15)),
            rng.uniform(18, 65, size=int(n * 0.60)),
            rng.uniform(65, 95, size=n - int(n * 0.05) - int(n * 0.15) - int(n * 0.60)),
        ]
    )
    rng.shuffle(ages)
    sex = rng.binomial(1, 0.5, size=n).astype(float)
    data: dict[str, np.ndarray] = {"age": ages, "sex": sex}
    for name in SYMPTOMS:
        data[f"sym_{name}"] = rng.binomial(1, SYMPTOM_PROBS[name], size=n).astype(float)
    spo2 = rng.normal(97, 2, size=n)
    spo2 -= 4 * np.maximum(data["sym_breathlessness"], data["sym_chest_pain"])
    pulse = rng.normal(82, 14, size=n)
    pulse += 18 * data["sym_fever"] + 6 * data["sym_chest_pain"]
    sbp = rng.normal(122, 18, size=n)
    sbp += 10 * (ages >= 65)
    dbp = rng.normal(78, 12, size=n)
    temp = rng.normal(37.0, 0.8, size=n)
    temp += 1.6 * data["sym_fever"]
    data["spo2"] = np.clip(spo2, 70, 100)
    data["pulse"] = np.clip(pulse, 30, 180)
    data["sbp"] = np.clip(sbp, 60, 240)
    data["dbp"] = np.clip(dbp, 30, 140)
    data["temp_c"] = np.clip(temp, 34, 42)
    for vital, prob in MISSING_PROBS.items():
        mask = rng.binomial(1, prob, size=n).astype(bool)
        data[vital] = np.where(mask, np.nan, data[vital])
    frame = pd.DataFrame(data)
    frame["age_band"] = frame["age"].map(age_band).astype(float)
    frame["shock_index"] = frame["pulse"] / frame["sbp"]
    frame["fever_flag"] = (frame["temp_c"] >= 38.0).astype(float)
    frame["hypoxia_flag"] = (frame["spo2"] < 94.0).astype(float)
    for vital in VITALS:
        frame[f"{vital}_missing"] = frame[vital].isna().astype(float)
    levels = []
    for _, row in frame.iterrows():
        plain = row.to_dict()
        for vital in VITALS + ["shock_index"]:
            value = plain.get(vital)
            if pd.isna(value):
                plain[vital] = None
        levels.append(transparent_level(plain))
    frame["level"] = np.array(levels, dtype=int)
    noise = rng.binomial(1, config.noise_rate, size=n).astype(bool)
    shift = rng.choice([-1, 1], size=n)
    frame.loc[noise, "level"] = np.clip(frame.loc[noise, "level"] + shift[noise], 1, 5)
    return frame[FEATURE_COLUMNS + ["level"]]


def impute_with_medians(frame: pd.DataFrame, medians: dict[str, float]) -> pd.DataFrame:
    filled = frame.copy()
    for column in FEATURE_COLUMNS:
        if column in filled and filled[column].isna().any():
            filled[column] = filled[column].fillna(medians.get(column, 0.0))
    return filled
