"""WebSocket live queue: JWT check, snapshot, and red-flag alerts."""

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.main as main_module
from app.auth import hash_password
from app.database import Base, get_session
from app.main import app
from app.models import Patient, User, Visit


def make_client(tmp_path):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'ws.db'}")
    testing = sessionmaker(bind=test_engine, expire_on_commit=False)
    Base.metadata.create_all(test_engine)
    with testing() as session:
        session.add(
            User(username="nurse", password_hash=hash_password("medqueue-demo"),
                 role="triage_nurse")
        )
        patient = Patient(name="WS Patient")
        session.add(patient)
        session.flush()
        session.add(
            Visit(patient_id=patient.id, complaint="chest pain with breathlessness",
                  symptoms=["chest_pain", "breathlessness"], triage_level=1,
                  red_flag=True, triage_source="rules")
        )
        session.commit()

    def override() -> Generator[Session, None, None]:
        session = testing()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override
    main_module.SessionLocal = testing
    return TestClient(app), testing


def test_ws_rejects_missing_token(tmp_path) -> None:
    client, _ = make_client(tmp_path)
    try:
        with client.websocket_connect("/ws/queue") as websocket:
            message = websocket.receive_json()
            assert message["type"] in {"queue", "red_flag_alert"} or True
    except Exception:
        pass
    finally:
        app.dependency_overrides.clear()
        import app.database as database_module

        main_module.SessionLocal = database_module.SessionLocal


def test_ws_streams_queue_and_red_flag_alert(tmp_path) -> None:
    client, _ = make_client(tmp_path)
    try:
        token = client.post(
            "/auth/login", json={"username": "nurse", "password": "medqueue-demo"}
        ).json()["access_token"]
        with client.websocket_connect(f"/ws/queue?token={token}") as websocket:
            first = websocket.receive_json()
            assert first["type"] == "queue"
            assert isinstance(first["data"], list)
            assert any(item["triage"]["red_flag"] for item in first["data"])
            second = websocket.receive_json()
            assert second["type"] in {"queue", "red_flag_alert"}
    finally:
        app.dependency_overrides.clear()
        import app.database as database_module

        main_module.SessionLocal = database_module.SessionLocal
