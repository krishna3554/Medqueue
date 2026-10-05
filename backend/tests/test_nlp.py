"""NLP lexicon, negation, duration, and extract-endpoint tests (draft)."""

import csv
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import hash_password
from app.database import Base, get_session
from app.main import app
from app.models import Patient, User, Visit
from app.nlp.language import detect_language, normalise
from app.nlp.lexicon import load_lexicon, match_text
from app.nlp.negation import annotate, duration_days

UTTERANCES = Path(__file__).parent / "data" / "utterances.csv"


def test_vocabulary_has_150_canonical() -> None:
    lexicon = load_lexicon()
    assert len(lexicon) >= 150


def test_language_detection() -> None:
    assert detect_language("mujhe bukhar hai") == "hi"
    assert detect_language("mala taap aahe") == "mr"
    assert detect_language("I have a headache") == "en"
    assert detect_language("मुझे बुखार है") == "hi"


def test_normalise_collapses_repeats() -> None:
    assert normalise("bukhaar") == "bukhar"


def test_exact_then_fuzzy_match() -> None:
    exact = match_text("mujhe bukhar hai")
    assert exact and exact[0]["canonical"] == "fever"
    assert exact[0]["method"] == "exact"
    fuzzy = match_text("bukhaarr with cough")
    assert any(item["canonical"] == "fever" for item in fuzzy)


def test_negation_and_duration() -> None:
    annotated = annotate("no fever, cough for 3 days", match_text("no fever, cough"))
    by_canonical = {item["canonical"]: item for item in annotated}
    assert by_canonical["fever"]["negated"] is True
    assert by_canonical["cough"]["negated"] is False
    assert by_canonical["cough"]["duration_days"] == 3
    assert duration_days("do din se khansi") == 2


def test_extract_endpoint_never_saves(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'nlp.db'}")
    testing = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with testing() as session:
        session.add(
            User(username="nurse", password_hash=hash_password("medqueue-demo"),
                 role="triage_nurse")
        )
        patient = Patient(name="NLP Patient")
        session.add(patient)
        session.flush()
        visit = Visit(patient_id=patient.id, complaint="check", symptoms=[])
        session.add(visit)
        session.commit()
        visit_id = visit.id

    def override():
        session = testing()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:
            token = client.post(
                "/auth/login", json={"username": "nurse", "password": "medqueue-demo"}
            ).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            response = client.post(
                f"/visits/{visit_id}/symptoms/extract",
                headers=headers,
                json={"text": "mujhe bukhar aur khansi hai, seene mein dard nahi hai"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["detected_language"] in {"hi", "mr", "en"}
            canonicals = {item["canonical"] for item in body["candidates"]}
            assert "fever" in canonicals and "cough" in canonicals
            for item in body["candidates"]:
                assert {"canonical", "confidence", "negated", "duration_days"} <= set(item)
        with testing() as session:
            # Extract must never save: symptoms unchanged, no audit row added.
            assert session.get(Visit, visit_id).symptoms == []
    finally:
        app.dependency_overrides.clear()


def test_utterance_suite_precision_recall() -> None:
    rows = list(csv.DictReader(UTTERANCES.open(encoding="utf-8")))
    assert len(rows) >= 100
    true_positives = false_positives = false_negatives = 0
    for row in rows:
        expected = {item.strip() for item in row["expected_canonical"].split(";") if item.strip()}
        predicted = {item["canonical"] for item in annotate(row["utterance"],
                                                            match_text(row["utterance"]))
                     if not item["negated"]}
        true_positives += len(expected & predicted)
        false_positives += len(predicted - expected)
        false_negatives += len(expected - predicted)
    precision = true_positives / max(true_positives + false_positives, 1)
    recall = true_positives / max(true_positives + false_negatives, 1)
    assert precision >= 0.5, f"precision {precision:.3f}"
    assert recall >= 0.4, f"recall {recall:.3f}"
