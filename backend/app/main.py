"""Authenticated API for the MedQueueAI prototype.

This service is deliberately rules-first and records human overrides as audit events.
It is decision support only and must not be used for clinical diagnosis.
"""

import os
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, engine, get_session
from app.models import AuditEvent, Patient, Visit, Vital
from app.queue.priority import priority
from app.triage.rules import load_rules
from app.triage.stub import stub_triage


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="MedQueueAI API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("MEDQUEUE_CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)
security = HTTPBearer()
JWT_SECRET = os.getenv("MEDQUEUE_JWT_SECRET", "development-secret-change-me")
ALGORITHM = "HS256"
RULES_PATH = Path(
    os.getenv("MEDQUEUE_RULES_PATH", Path(__file__).parents[2] / "docs" / "red_flag_rules.yaml")
)
RULES = load_rules(RULES_PATH)
KOLKATA = ZoneInfo("Asia/Kolkata")


class LoginRequest(BaseModel):
    username: str
    password: str


class PatientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    date_of_birth: date | None = None


class VisitCreate(BaseModel):
    patient_id: int
    complaint: str = Field(min_length=1, max_length=2_000)
    symptoms: list[str] = Field(default_factory=list)


class VitalsCreate(BaseModel):
    values: dict[str, float] = Field(min_length=1)


class SymptomsCreate(BaseModel):
    symptoms: list[str] = Field(default_factory=list)


class OverrideCreate(BaseModel):
    level: int = Field(ge=1, le=5)
    reason: str = Field(min_length=3, max_length=2_000)


class StatusChange(BaseModel):
    status: Literal["waiting", "in_review", "completed"]


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> dict[str, str]:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[ALGORITHM])
        username, role = payload["sub"], payload["role"]
    except (jwt.PyJWTError, KeyError) as error:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from error
    return {"username": username, "role": role}


def require_clinician(user: Annotated[dict[str, str], Depends(current_user)]) -> dict[str, str]:
    if user["role"] not in {"triage_nurse", "clinician", "admin"}:
        raise HTTPException(status_code=403, detail="Clinical role required")
    return user


def age_on(dob: str | None) -> int | None:
    if not dob:
        return None
    born = date.fromisoformat(dob)
    today = datetime.now(KOLKATA).date()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def latest_vitals(session: Session, visit_id: int) -> dict[str, float]:
    vital = session.scalars(
        select(Vital).where(Vital.visit_id == visit_id).order_by(Vital.recorded_at.desc())
    ).first()
    return vital.values if vital else {}


def triage_visit(session: Session, visit: Visit, patient: Patient) -> None:
    result = stub_triage(
        set(visit.symptoms), latest_vitals(session, visit.id), age_on(patient.date_of_birth), RULES
    )
    visit.triage_level = result["level"]
    visit.red_flag = result["red_flag"]
    visit.factors = result["factors"]
    visit.triage_source = result["source"]


def audit(
    session: Session, visit_id: int, actor: str, action: str, detail: dict[str, object]
) -> None:
    session.add(AuditEvent(visit_id=visit_id, actor=actor, action=action, detail=detail))


def visit_payload(
    session: Session, visit: Visit, patient: Patient, now: datetime
) -> dict[str, Any]:
    registered_at = visit.registered_at
    if registered_at.tzinfo is None:
        # SQLite does not preserve timezone information for DateTime columns.
        registered_at = registered_at.replace(tzinfo=UTC)
    effective_level = visit.override_level or visit.triage_level
    return {
        "id": visit.id,
        "patient": {"id": patient.id, "name": patient.name, "date_of_birth": patient.date_of_birth},
        "complaint": visit.complaint,
        "symptoms": visit.symptoms,
        "registered_at": registered_at,
        "status": visit.status,
        "triage": {
            "level": effective_level,
            "automated_level": visit.triage_level,
            "red_flag": visit.red_flag,
            "factors": visit.factors,
            "source": visit.triage_source,
            "overridden": visit.override_level is not None,
        },
        "latest_vitals": latest_vitals(session, visit.id),
        "priority_score": round(priority(effective_level, registered_at, now, visit.red_flag), 3),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login")
def login(payload: LoginRequest) -> dict[str, str]:
    # Prototype-only account. A production deployment must use an identity provider.
    if (payload.username, payload.password) != ("triage", "medqueue-demo"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = jwt.encode(
        {
            "sub": payload.username,
            "role": "triage_nurse",
            "exp": datetime.now(UTC) + timedelta(hours=8),
        },
        JWT_SECRET,
        algorithm=ALGORITHM,
    )
    return {"access_token": token, "token_type": "bearer"}


@app.post("/patients", status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[dict[str, str], Depends(require_clinician)],
) -> dict[str, object]:
    patient = Patient(
        name=payload.name,
        date_of_birth=payload.date_of_birth.isoformat() if payload.date_of_birth else None,
    )
    session.add(patient)
    session.commit()
    return {"id": patient.id, "name": patient.name, "date_of_birth": patient.date_of_birth}


@app.post("/visits", status_code=status.HTTP_201_CREATED)
def create_visit(
    payload: VisitCreate,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[dict[str, str], Depends(require_clinician)],
) -> dict[str, Any]:
    patient = session.get(Patient, payload.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    visit = Visit(
        patient_id=patient.id, complaint=payload.complaint, symptoms=sorted(set(payload.symptoms))
    )
    session.add(visit)
    session.flush()
    triage_visit(session, visit, patient)
    audit(
        session,
        visit.id,
        user["username"],
        "visit_registered",
        {"triage_level": visit.triage_level},
    )
    session.commit()
    return visit_payload(session, visit, patient, datetime.now(UTC))


@app.post("/visits/{visit_id}/vitals")
def record_vitals(
    visit_id: int,
    payload: VitalsCreate,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[dict[str, str], Depends(require_clinician)],
) -> dict[str, Any]:
    visit = session.get(Visit, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    patient = session.get(Patient, visit.patient_id)
    assert patient is not None
    session.add(Vital(visit_id=visit.id, values=payload.values))
    session.flush()
    triage_visit(session, visit, patient)
    audit(session, visit.id, user["username"], "vitals_recorded", {"values": payload.values})
    session.commit()
    return visit_payload(session, visit, patient, datetime.now(UTC))


@app.post("/visits/{visit_id}/symptoms")
def record_symptoms(
    visit_id: int,
    payload: SymptomsCreate,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[dict[str, str], Depends(require_clinician)],
) -> dict[str, Any]:
    """Replace the confirmed canonical symptom list and re-run rules-first triage."""
    visit = session.get(Visit, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    patient = session.get(Patient, visit.patient_id)
    assert patient is not None
    visit.symptoms = sorted({item.strip().lower() for item in payload.symptoms if item.strip()})
    triage_visit(session, visit, patient)
    audit(session, visit.id, user["username"], "symptoms_recorded", {"symptoms": visit.symptoms})
    session.commit()
    return visit_payload(session, visit, patient, datetime.now(UTC))


@app.get("/queue")
def queue(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[dict[str, str], Depends(current_user)],
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    rows = session.execute(
        select(Visit, Patient).join(Patient).where(Visit.status == "waiting")
    ).all()
    return sorted(
        (visit_payload(session, visit, patient, now) for visit, patient in rows),
        key=lambda item: (-item["priority_score"], item["registered_at"]),
    )


@app.post("/visits/{visit_id}/override")
def override_priority(
    visit_id: int,
    payload: OverrideCreate,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[dict[str, str], Depends(require_clinician)],
) -> dict[str, Any]:
    visit = session.get(Visit, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    patient = session.get(Patient, visit.patient_id)
    assert patient is not None
    visit.override_level, visit.override_reason, visit.override_by = (
        payload.level,
        payload.reason,
        user["username"],
    )
    audit(
        session,
        visit.id,
        user["username"],
        "priority_overridden",
        {"level": payload.level, "reason": payload.reason},
    )
    session.commit()
    return visit_payload(session, visit, patient, datetime.now(UTC))


@app.patch("/visits/{visit_id}/status")
def update_status(
    visit_id: int,
    payload: StatusChange,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[dict[str, str], Depends(require_clinician)],
) -> dict[str, str]:
    visit = session.get(Visit, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    visit.status = payload.status
    audit(session, visit.id, user["username"], "status_changed", {"status": payload.status})
    session.commit()
    return {"id": str(visit.id), "status": visit.status}


@app.get("/visits/{visit_id}/audit")
def visit_audit(
    visit_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[dict[str, str], Depends(current_user)],
) -> list[dict[str, Any]]:
    if not session.get(Visit, visit_id):
        raise HTTPException(status_code=404, detail="Visit not found")
    events = session.scalars(
        select(AuditEvent).where(AuditEvent.visit_id == visit_id).order_by(AuditEvent.created_at)
    ).all()
    return [
        {
            "id": event.id,
            "actor": event.actor,
            "action": event.action,
            "detail": event.detail,
            "created_at": event.created_at,
        }
        for event in events
    ]
