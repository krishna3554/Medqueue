"""Phase 2: rules-first model triage and deterministic explanations."""

import os
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth import hash_password
from app.database import Base, get_session
from app.explain.shap_service import explain
from app.main import app
from app.models import User
from app.triage import model as triage_model


def make_client(tmp_path):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    testing_session = sessionmaker(bind=test_engine, expire_on_commit=False)
    Base.metadata.create_all(test_engine)
    with testing_session() as session:
        session.add(
            User(username="nurse", password_hash=hash_password("medqueue-demo"),
                 role="triage_nurse")
        )
        session.commit()

    def test_session() -> Generator[Session, None, None]:
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = test_session
    return TestClient(app)


def auth_headers(client):
    login = client.post("/auth/login",
                        json={"username": "nurse", "password": "medqueue-demo"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_same_input_gives_same_explanation() -> None:
    first = explain({"fever"}, {"temp_c": 39.4, "pulse": 118}, 30, 2)
    second = explain({"fever"}, {"temp_c": 39.4, "pulse": 118}, 30, 2)
    assert first == second
    assert len(first["top_factors"]) == 3
    assert first["rationale"].startswith("Urgency raised by:")
    for factor in first["top_factors"]:
        assert {"name", "value", "contribution"} <= set(factor)


def test_missing_vitals_handled() -> None:
    result = triage_model.predict(set(), {}, None)
    assert result is not None
    assert result["level"] in {1, 2, 3, 4, 5}
    details = explain(set(), {}, None, result["level"])
    assert len(details["top_factors"]) == 3


def test_rule_match_overrides_model(tmp_path) -> None:
    client = make_client(tmp_path)
    try:
        headers = auth_headers(client)
        patient = client.post("/patients", headers=headers, json={"name": "Rule"})
        pid = patient.json()["id"]
        visit = client.post(
            "/visits", headers=headers,
            json={"patient_id": pid, "complaint": "chest pain",
                  "symptoms": ["chest_pain", "breathlessness"]},
        )
        assert visit.status_code == 201
        triage = visit.json()["triage"]
        assert triage["red_flag"] is True
        assert triage["level"] == 1
        assert triage["source"] == "rules"
    finally:
        app.dependency_overrides.clear()


def test_model_missing_falls_back_without_error(tmp_path, monkeypatch) -> None:
    triage_model.reset_cache()
    monkeypatch.setenv("MEDQUEUE_MODEL_DIR", str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir(exist_ok=True)
    try:
        assert triage_model.predict({"cough"}, {}, 30) is None
        client = make_client(tmp_path)
        try:
            headers = auth_headers(client)
            patient = client.post("/patients", headers=headers, json={"name": "Fallback"})
            visit = client.post(
                "/visits", headers=headers,
                json={"patient_id": patient.json()["id"], "complaint": "cough",
                      "symptoms": ["cough"]},
            )
            assert visit.status_code == 201
            # Never blocks registration; falls back to rules + stub.
            assert visit.json()["triage"]["source"] == "stub"
            assert visit.json()["triage"]["ai_available"] is False
        finally:
            app.dependency_overrides.clear()
    finally:
        monkeypatch.delenv("MEDQUEUE_MODEL_DIR", raising=False)
        triage_model.reset_cache()
        assert os.getenv("MEDQUEUE_MODEL_DIR") is None


def test_model_visit_stores_version_and_factors(tmp_path) -> None:
    triage_model.reset_cache()
    client = make_client(tmp_path)
    try:
        headers = auth_headers(client)
        patient = client.post("/patients", headers=headers, json={"name": "Model"})
        visit = client.post(
            "/visits", headers=headers,
            json={"patient_id": patient.json()["id"], "complaint": "fever",
                  "symptoms": ["fever"]},
        )
        triage = visit.json()["triage"]
        if triage["source"] == "model":
            assert triage["model_version"] == triage_model.model_version()
            assert isinstance(triage["top_factors"], list)
            assert len(triage["top_factors"]) == 3
    finally:
        app.dependency_overrides.clear()
        triage_model.reset_cache()
