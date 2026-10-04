from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth import hash_password
from app.database import Base, get_session
from app.main import app
from app.models import AuditEvent, User


def test_triage_workflow_is_ranked_and_audited(tmp_path) -> None:
    test_engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    testing_session = sessionmaker(bind=test_engine, expire_on_commit=False)
    Base.metadata.create_all(test_engine)
    with testing_session() as session:
        session.add(
            User(
                username="nurse",
                password_hash=hash_password("medqueue-demo"),
                role="triage_nurse",
            )
        )
        session.commit()

    def test_session() -> Generator[Session, None, None]:
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = test_session
    try:
        with TestClient(app) as client:
            login = client.post(
                "/auth/login", json={"username": "nurse", "password": "medqueue-demo"}
            )
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            patient = client.post(
                "/patients", headers=headers, json={"name": "Anita", "date_of_birth": "1968-01-01"}
            )
            assert patient.status_code == 201
            visit = client.post(
                "/visits",
                headers=headers,
                json={
                    "patient_id": patient.json()["id"],
                    "complaint": "chest tightness",
                    "symptoms": ["chest_tightness"],
                },
            )
            assert visit.status_code == 201
            visit_id = visit.json()["id"]
            # Rules-first: chest_tightness alone matches no red-flag rule,
            # so the synthetic model decides (source model, AI available).
            assert visit.json()["triage"]["source"] == "model"
            assert visit.json()["triage"]["model_version"] == "synthetic-v0.1"
            assert visit.json()["triage"]["level"] in {1, 2, 3, 4, 5}

            vitals = client.post(
                f"/visits/{visit_id}/vitals", headers=headers, json={"values": {"spo2": 91}}
            )
            assert vitals.status_code == 200
            assert vitals.json()["triage"]["red_flag"] is True
            assert vitals.json()["triage"]["level"] == 1

            queue = client.get("/queue", headers=headers)
            assert queue.status_code == 200
            assert queue.json()[0]["id"] == visit_id

            override = client.post(
                f"/visits/{visit_id}/override",
                headers=headers,
                json={"level": 2, "reason": "Clinician reassessment"},
            )
            assert override.status_code == 200
            assert override.json()["triage"]["overridden"] is True

        with testing_session() as session:
            actions = session.scalars(
                select(AuditEvent.action).where(AuditEvent.visit_id == visit_id)
            ).all()
            assert actions == ["visit_registered", "vitals_recorded", "priority_overridden"]
    finally:
        app.dependency_overrides.clear()
