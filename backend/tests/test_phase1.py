"""Phase 1: roles, doctors, wait estimates, and override semantics."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth import hash_password
from app.database import Base, get_session
from app.main import app, effective_level
from app.models import Doctor, User, Visit
from app.queue.priority import priority


def make_client(tmp_path, users=(("registration", "registration"), ("nurse", "triage_nurse"),
                                 ("clinician", "clinician"), ("admin", "admin"))):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    testing_session = sessionmaker(bind=test_engine, expire_on_commit=False)
    Base.metadata.create_all(test_engine)
    with testing_session() as session:
        for username, role in users:
            session.add(
                User(
                    username=username,
                    password_hash=hash_password("medqueue-demo"),
                    role=role,
                )
            )
        session.add(
            Doctor(name="Dr Test", department="General", status="available",
                   avg_consult_min=10.0)
        )
        session.commit()

    def test_session() -> Generator[Session, None, None]:
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = test_session
    return TestClient(app), testing_session


def auth_headers(client, username):
    login = client.post(
        "/auth/login", json={"username": username, "password": "medqueue-demo"}
    )
    assert login.status_code == 200, login.text
    assert login.json()["role"] in {"registration", "triage_nurse", "clinician", "admin"}
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_invalid_login_rejected(tmp_path) -> None:
    client, _ = make_client(tmp_path)
    try:
        bad = client.post("/auth/login", json={"username": "nurse", "password": "wrong"})
        assert bad.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_registration_can_register_but_cannot_override(tmp_path) -> None:
    client, _ = make_client(tmp_path)
    try:
        reg = auth_headers(client, "registration")
        patient = client.post(
            "/patients", headers=reg, json={"name": "Reg Patient"}
        )
        assert patient.status_code == 201, patient.text
        visit = client.post(
            "/visits",
            headers=reg,
            json={"patient_id": patient.json()["id"], "complaint": "cough",
                  "symptoms": ["cough"]},
        )
        assert visit.status_code == 201, visit.text
        visit_id = visit.json()["id"]
        denied = client.post(
            f"/visits/{visit_id}/override",
            headers=reg,
            json={"level": 1, "reason": "trying to escalate"},
        )
        assert denied.status_code == 403
        denied_status = client.patch(
            f"/visits/{visit_id}/status", headers=reg, json={"status": "in_review"}
        )
        assert denied_status.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_audit_requires_admin(tmp_path) -> None:
    client, _ = make_client(tmp_path)
    try:
        nurse = auth_headers(client, "nurse")
        admin = auth_headers(client, "admin")
        patient = client.post("/patients", headers=nurse, json={"name": "Audit Patient"})
        visit = client.post(
            "/visits",
            headers=nurse,
            json={"patient_id": patient.json()["id"], "complaint": "fever",
                  "symptoms": []},
        )
        visit_id = visit.json()["id"]
        assert client.get(f"/visits/{visit_id}/audit", headers=nurse).status_code == 403
        ok = client.get(f"/visits/{visit_id}/audit", headers=admin)
        assert ok.status_code == 200
        assert any(event["action"] == "visit_registered" for event in ok.json())
    finally:
        app.dependency_overrides.clear()


def test_doctor_endpoints_and_assignment(tmp_path) -> None:
    client, testing_session = make_client(tmp_path)
    try:
        nurse = auth_headers(client, "nurse")
        reg = auth_headers(client, "registration")
        doctors = client.get("/doctors", headers=reg)
        assert doctors.status_code == 200
        assert len(doctors.json()) == 1
        doctor_id = doctors.json()[0]["id"]
        # Clinical role may update status; registration is not clinical.
        forbidden = client.patch(
            f"/doctors/{doctor_id}/status", headers=reg, json={"status": "break"}
        )
        assert forbidden.status_code == 403
        ok = client.patch(
            f"/doctors/{doctor_id}/status", headers=nurse, json={"status": "break"}
        )
        assert ok.status_code == 200
        assert ok.json()["status"] == "break"
        patient = client.post("/patients", headers=nurse, json={"name": "Doc Patient"})
        visit = client.post(
            "/visits",
            headers=nurse,
            json={"patient_id": patient.json()["id"], "complaint": "checkup",
                  "symptoms": []},
        )
        visit_id = visit.json()["id"]
        assigned = client.patch(
            f"/visits/{visit_id}/doctor", headers=nurse, json={"doctor_id": doctor_id}
        )
        assert assigned.status_code == 200
        assert assigned.json()["doctor_id"] == doctor_id
        with testing_session() as session:
            assert session.get(Visit, visit_id).doctor_id == doctor_id
    finally:
        app.dependency_overrides.clear()


def test_queue_wait_uses_doctor_estimates_and_records_consult_times(tmp_path) -> None:
    client, testing_session = make_client(tmp_path)
    try:
        nurse = auth_headers(client, "nurse")
        doctors = client.get("/doctors", headers=nurse).json()
        doctor_id = doctors[0]["id"]
        patient = client.post("/patients", headers=nurse, json={"name": "Wait Patient"})
        pid = patient.json()["id"]
        first = client.post(
            "/visits", headers=nurse,
            json={"patient_id": pid, "complaint": "first", "symptoms": [],
                  "doctor_id": doctor_id},
        ).json()
        second = client.post(
            "/visits", headers=nurse,
            json={"patient_id": pid, "complaint": "second", "symptoms": [],
                  "doctor_id": doctor_id},
        ).json()
        queue = client.get("/queue", headers=nurse)
        assert queue.status_code == 200
        items = {item["id"]: item for item in queue.json()}
        assert items[first["id"]]["est_wait_min"] == 0.0
        # Second patient waits for one 10-minute consult ahead with the same doctor.
        assert items[second["id"]]["est_wait_min"] == 10.0
        # Status changes record consultation timestamps.
        started = client.patch(
            f"/visits/{first['id']}/status", headers=nurse, json={"status": "in_review"}
        )
        assert started.status_code == 200
        completed = client.patch(
            f"/visits/{first['id']}/status", headers=nurse, json={"status": "completed"}
        )
        assert completed.status_code == 200
        with testing_session() as session:
            visit = session.get(Visit, first["id"])
            assert visit.consult_started_at is not None
            assert visit.consult_ended_at is not None
            assert visit.consult_ended_at >= visit.consult_started_at
    finally:
        app.dependency_overrides.clear()


def test_override_replaces_level_but_red_flag_and_aging_still_apply() -> None:
    now = datetime.now(UTC)
    registered = now - timedelta(minutes=30)
    visit = Visit(
        patient_id=1, complaint="test", symptoms=[], triage_level=4, red_flag=True,
        override_level=2,
    )
    assert effective_level(visit) == 2
    # Documented semantics: override replaces the base level, but red_flag and
    # waiting-time aging still flow into priority().
    assert priority(2, registered, now, True) > priority(2, registered, now, False)
    assert priority(2, registered, now, True) > priority(2, now, now, True)
    assert effective_level(
        Visit(patient_id=1, complaint="t", symptoms=[], triage_level=4, red_flag=False)
    ) == 4


def test_unassigned_wait_is_pooled_across_available_doctors(tmp_path) -> None:
    client, testing_session = make_client(tmp_path)
    try:
        nurse = auth_headers(client, "nurse")
        with testing_session() as session:
            session.add(
                Doctor(name="Dr Second", department="General", status="available",
                       avg_consult_min=10.0)
            )
            session.commit()
        patient = client.post("/patients", headers=nurse, json={"name": "Pool"})
        pid = patient.json()["id"]
        client.post(
            "/visits", headers=nurse,
            json={"patient_id": pid, "complaint": "a", "symptoms": []},
        )
        client.post(
            "/visits", headers=nurse,
            json={"patient_id": pid, "complaint": "b", "symptoms": []},
        )
        queue = client.get("/queue", headers=nurse).json()
        assert len(queue) == 2
        # One 10-minute consult ahead pooled across 2 available doctors = 5.0 min.
        assert queue[1]["est_wait_min"] == 5.0
    finally:
        app.dependency_overrides.clear()
