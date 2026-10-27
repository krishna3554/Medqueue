from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth import hash_password
from app.database import Base, get_session
from app.main import app
from app.models import User


def make_client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'features.db'}")
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with sessions.begin() as session:
        session.add_all(
            [
                User(username="admin", password_hash=hash_password("password"), role="admin"),
                User(
                    username="registration",
                    password_hash=hash_password("password"),
                    role="registration",
                ),
            ]
        )

    def test_session() -> Generator[Session, None, None]:
        session = sessions()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = test_session
    return TestClient(app)


def token(client: TestClient, username: str) -> str:
    response = client.post("/auth/login", json={"username": username, "password": "password"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_profile_and_read_only_assistant_are_role_aware(tmp_path) -> None:
    client = make_client(tmp_path)
    try:
        registration = {"Authorization": f"Bearer {token(client, 'registration')}"}
        profile = client.get("/me", headers=registration)
        assert profile.json()["department"] == "Registration"
        general = client.post(
            "/assistant/explain", headers=registration, json={"question": "How does queue work?"}
        )
        assert general.status_code == 200
        denied = client.post(
            "/assistant/explain",
            headers=registration,
            json={"question": "Why?", "visit_id": 1},
        )
        assert denied.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_analytics_is_admin_only(tmp_path) -> None:
    client = make_client(tmp_path)
    try:
        admin = {"Authorization": f"Bearer {token(client, 'admin')}"}
        result = client.get("/analytics/overview", headers=admin)
        assert result.status_code == 200
        assert result.json()["synthetic_only"] is True
    finally:
        app.dependency_overrides.clear()
