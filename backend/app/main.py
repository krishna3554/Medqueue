"""Authenticated API for the MedQueueAI prototype.

This service is deliberately rules-first and records human overrides as audit events.
It is decision support only and must not be used for clinical diagnosis.
"""

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
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

from app.auth import verify_password
from app.database import Base, engine, get_session
from app.explain.shap_service import explain
from app.models import AuditEvent, Doctor, Patient, User, Visit, Vital
from app.nlp.language import detect_language
from app.nlp.lexicon import match_text
from app.nlp.negation import annotate
from app.queue.priority import priority
from app.queue.wait import RollingMean, estimate_wait_min
from app.triage import model as triage_model
from app.triage.rules import evaluate_rules, load_rules
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
DEPT_DEFAULT_MIN = 10.0


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
    doctor_id: int | None = None


class VitalsCreate(BaseModel):
    values: dict[str, float] = Field(min_length=1)


class SymptomsCreate(BaseModel):
    symptoms: list[str] = Field(default_factory=list)


class SymptomsExtract(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)
    language: str | None = None


class OverrideCreate(BaseModel):
    level: int = Field(ge=1, le=5)
    reason: str = Field(min_length=3, max_length=2_000)


class StatusChange(BaseModel):
    status: Literal["waiting", "in_review", "completed"]


class DoctorStatusChange(BaseModel):
    status: Literal["available", "break", "off"]


class DoctorAssign(BaseModel):
    doctor_id: int | None


@dataclass
class AheadEntry:
    doctor_id: str | None


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


def require_admin(user: Annotated[dict[str, str], Depends(current_user)]) -> dict[str, str]:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
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
    """Rules-first triage: red-flag rules override any model output.

    Falls back to rules + stub with an "AI unavailable" state when the model
    is missing or fails. Never raises because of the model.
    """
    symptoms = set(visit.symptoms)
    vitals = latest_vitals(session, visit.id)
    years = age_on(patient.date_of_birth)
    if evaluate_rules(symptoms, vitals, years, RULES):
        result = stub_triage(symptoms, vitals, years, RULES)
        visit.triage_level = result["level"]
        visit.red_flag = result["red_flag"]
        visit.factors = result["factors"]
        visit.triage_source = result["source"]
        visit.top_factors = None
        visit.model_version = None
        return
    predicted = triage_model.predict(symptoms, vitals, years)
    if predicted is not None:
        level = int(predicted["level"])
        details = explain(symptoms, vitals, years, level)
        visit.triage_level = level
        visit.red_flag = False
        visit.factors = [details["rationale"]]
        visit.triage_source = "model"
        visit.top_factors = details["top_factors"]
        visit.model_version = str(predicted["model_version"])
        return
    result = stub_triage(symptoms, vitals, years, RULES)
    visit.triage_level = result["level"]
    visit.red_flag = result["red_flag"]
    visit.factors = result["factors"]
    visit.triage_source = result["source"]
    visit.top_factors = None
    visit.model_version = None


def audit(
    session: Session, visit_id: int, actor: str, action: str, detail: dict[str, object]
) -> None:
    session.add(AuditEvent(visit_id=visit_id, actor=actor, action=action, detail=detail))


def effective_level(visit: Visit) -> int:
    """Override replaces the base triage level; red-flag and aging still apply.

    The returned level feeds priority() together with the stored red_flag and
    registered_at, so waiting-time aging and the red-flag boost are unchanged
    by an override. The automated level is preserved for audit.
    """
    return visit.override_level if visit.override_level is not None else visit.triage_level


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def consultation_estimates(session: Session) -> tuple[dict[str | None, float], float, int]:
    """Per-doctor consult means from recent durations with department fallback.

    Uses RollingMean (min 3 samples per doctor) fed from stored consultation
    start/end times; falls back to each doctor's avg_consult_min and then to
    the department mean. Returns (avg_map, dept_default, available_count).
    """
    doctors = session.scalars(select(Doctor)).all()
    if not doctors:
        return {}, DEPT_DEFAULT_MIN, 0
    available = [item for item in doctors if item.status == "available"] or list(doctors)
    dept_default = sum(item.avg_consult_min for item in available) / len(available)
    rolling = RollingMean()
    recent = session.scalars(
        select(Visit)
        .where(Visit.consult_started_at.is_not(None), Visit.consult_ended_at.is_not(None))
        .order_by(Visit.consult_ended_at.desc())
        .limit(200)
    ).all()
    for item in recent:
        if item.doctor_id is None:
            continue
        minutes = (
            ensure_utc(item.consult_ended_at) - ensure_utc(item.consult_started_at)
        ).total_seconds() / 60
        if 0 <= minutes <= 240:
            rolling.add(str(item.doctor_id), minutes)
    avg_map: dict[str | None, float] = {
        str(item.id): rolling.for_doctor(str(item.id), item.avg_consult_min)
        for item in doctors
    }
    count = sum(1 for item in doctors if item.status == "available")
    return avg_map, dept_default, count


def visit_payload(
    session: Session, visit: Visit, patient: Patient, now: datetime,
    est_wait_min: float | None = None,
) -> dict[str, Any]:
    registered_at = ensure_utc(visit.registered_at)
    level = effective_level(visit)
    return {
        "id": visit.id,
        "patient": {"id": patient.id, "name": patient.name, "date_of_birth": patient.date_of_birth},
        "complaint": visit.complaint,
        "symptoms": visit.symptoms,
        "registered_at": registered_at,
        "status": visit.status,
        "doctor_id": visit.doctor_id,
        "consult_started_at": visit.consult_started_at,
        "consult_ended_at": visit.consult_ended_at,
        "triage": {
            "level": level,
            "automated_level": visit.triage_level,
            "red_flag": visit.red_flag,
            "factors": visit.factors,
            "source": visit.triage_source,
            "overridden": visit.override_level is not None,
            "top_factors": visit.top_factors,
            "model_version": visit.model_version,
            "ai_available": visit.triage_source == "model" or visit.model_version is not None,
        },
        "latest_vitals": latest_vitals(session, visit.id),
        "priority_score": round(priority(level, registered_at, now, visit.red_flag), 3),
        "est_wait_min": est_wait_min,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login")
def login(
    payload: LoginRequest, session: Annotated[Session, Depends(get_session)]
) -> dict[str, str]:
    """Authenticate a seeded dev user; production must use an identity provider."""
    user = session.scalars(select(User).where(User.username == payload.username)).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = jwt.encode(
        {
            "sub": user.username,
            "role": user.role,
            "exp": datetime.now(UTC) + timedelta(hours=8),
        },
        JWT_SECRET,
        algorithm=ALGORITHM,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
    }


@app.post("/patients", status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[dict[str, str], Depends(current_user)],
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
    user: Annotated[dict[str, str], Depends(current_user)],
) -> dict[str, Any]:
    patient = session.get(Patient, payload.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if payload.doctor_id is not None and not session.get(Doctor, payload.doctor_id):
        raise HTTPException(status_code=404, detail="Doctor not found")
    visit = Visit(
        patient_id=patient.id,
        complaint=payload.complaint,
        symptoms=sorted(set(payload.symptoms)),
        doctor_id=payload.doctor_id,
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
    user: Annotated[dict[str, str], Depends(current_user)],
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
    user: Annotated[dict[str, str], Depends(current_user)],
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


@app.post("/visits/{visit_id}/symptoms/extract")
def extract_symptoms(
    visit_id: int,
    payload: SymptomsExtract,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[dict[str, str], Depends(current_user)],
) -> dict[str, Any]:
    """Return candidate canonical symptoms without saving anything.

    Draft lexicon lookup (exact then fuzzy) with negation and duration
    handling. The caller must confirm via POST /visits/{visit_id}/symptoms.
    """
    if not session.get(Visit, visit_id):
        raise HTTPException(status_code=404, detail="Visit not found")
    language = payload.language or detect_language(payload.text)
    candidates = annotate(payload.text, match_text(payload.text))
    return {"detected_language": language, "candidates": candidates}


@app.get("/queue")
def queue(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[dict[str, str], Depends(current_user)],
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    rows = session.execute(
        select(Visit, Patient).join(Patient).where(Visit.status == "waiting")
    ).all()
    ranked = sorted(
        (visit_payload(session, visit, patient, now) for visit, patient in rows),
        key=lambda item: (-item["priority_score"], item["registered_at"]),
    )
    avg_map, dept_default, available_count = consultation_estimates(session)
    divisor = available_count or 1
    for index, item in enumerate(ranked):
        doctor_key = str(item["doctor_id"]) if item["doctor_id"] is not None else None
        if doctor_key is not None:
            ahead = [
                AheadEntry(str(other["doctor_id"]))
                for other in ranked[:index]
                if other["doctor_id"] == item["doctor_id"]
            ]
            item["est_wait_min"] = estimate_wait_min(ahead, avg_map, dept_default)
        else:
            ahead = [
                AheadEntry(str(other["doctor_id"]) if other["doctor_id"] is not None else None)
                for other in ranked[:index]
            ]
            total = estimate_wait_min(ahead, avg_map, dept_default)
            item["est_wait_min"] = round(total / divisor, 1)
    return ranked


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
    now = datetime.now(UTC)
    visit.status = payload.status
    if payload.status == "in_review" and visit.consult_started_at is None:
        visit.consult_started_at = now
    if payload.status == "completed":
        if visit.consult_started_at is None:
            visit.consult_started_at = now
        visit.consult_ended_at = now
    audit(session, visit.id, user["username"], "status_changed", {"status": payload.status})
    session.commit()
    return {"id": str(visit.id), "status": visit.status}


@app.patch("/visits/{visit_id}/doctor")
def assign_doctor(
    visit_id: int,
    payload: DoctorAssign,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[dict[str, str], Depends(require_clinician)],
) -> dict[str, Any]:
    visit = session.get(Visit, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if payload.doctor_id is not None and not session.get(Doctor, payload.doctor_id):
        raise HTTPException(status_code=404, detail="Doctor not found")
    patient = session.get(Patient, visit.patient_id)
    assert patient is not None
    visit.doctor_id = payload.doctor_id
    audit(
        session, visit.id, user["username"], "doctor_assigned", {"doctor_id": payload.doctor_id}
    )
    session.commit()
    return visit_payload(session, visit, patient, datetime.now(UTC))


@app.get("/doctors")
def list_doctors(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[dict[str, str], Depends(current_user)],
) -> list[dict[str, Any]]:
    doctors = session.scalars(select(Doctor).order_by(Doctor.id)).all()
    return [
        {
            "id": item.id,
            "name": item.name,
            "department": item.department,
            "status": item.status,
            "avg_consult_min": item.avg_consult_min,
        }
        for item in doctors
    ]


@app.patch("/doctors/{doctor_id}/status")
def update_doctor_status(
    doctor_id: int,
    payload: DoctorStatusChange,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[dict[str, str], Depends(require_clinician)],
) -> dict[str, Any]:
    doctor = session.get(Doctor, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    doctor.status = payload.status
    session.commit()
    return {
        "id": doctor.id,
        "name": doctor.name,
        "department": doctor.department,
        "status": doctor.status,
        "avg_consult_min": doctor.avg_consult_min,
    }


@app.get("/visits/{visit_id}/audit")
def visit_audit(
    visit_id: int,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[dict[str, str], Depends(require_admin)],
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
