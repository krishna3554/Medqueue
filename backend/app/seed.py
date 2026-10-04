"""Populate the local prototype database with clearly synthetic demo records.

Run with: ``python -m app.seed`` from the backend directory.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.auth import VALID_ROLES, hash_password
from app.database import Base, SessionLocal, engine
from app.models import AuditEvent, Doctor, Patient, User, Visit, Vital
from app.triage.rules import load_rules
from app.triage.stub import stub_triage

DEMO_PATIENTS = [
    {
        "name": "Demo Anita Rao",
        "date_of_birth": "1968-04-12",
        "complaint": "Chest tightness and breathlessness",
        "symptoms": ["chest_tightness", "breathlessness"],
        "vitals": {"spo2": 91, "pulse": 118, "sbp": 148, "temp_c": 37.2},
        "wait_min": 3,
    },
    {
        "name": "Demo Farhan Khan",
        "date_of_birth": "1995-09-20",
        "complaint": "High fever for three days",
        "symptoms": ["fever"],
        "vitals": {"temp_c": 39.4, "pulse": 112},
        "wait_min": 11,
    },
    {
        "name": "Demo Meera Shah",
        "date_of_birth": "1984-01-08",
        "complaint": "Severe abdominal pain",
        "symptoms": ["abdominal_pain"],
        "vitals": {"pulse": 106, "sbp": 124},
        "wait_min": 19,
    },
    {
        "name": "Demo Gaurav Patel",
        "date_of_birth": "1959-07-15",
        "complaint": "Dizziness",
        "symptoms": ["dizziness"],
        "vitals": {"sbp": 178, "pulse": 84},
        "wait_min": 27,
    },
    {
        "name": "Demo Kavita Joshi",
        "date_of_birth": "2002-11-03",
        "complaint": "Persistent cough",
        "symptoms": ["cough"],
        "vitals": {"temp_c": 37.2, "spo2": 98},
        "wait_min": 36,
    },
    {
        "name": "Demo Joseph Dsouza",
        "date_of_birth": "1976-03-25",
        "complaint": "Medication refill",
        "symptoms": [],
        "vitals": {},
        "wait_min": 48,
    },
]


DEV_USERS = [
    {"username": "registration", "role": "registration"},
    {"username": "nurse", "role": "triage_nurse"},
    {"username": "clinician", "role": "clinician"},
    {"username": "admin", "role": "admin"},
]
DEV_PASSWORD = "medqueue-demo"

DEMO_DOCTORS = [
    {"name": "Dr. A. General", "department": "General", "status": "available",
     "avg_consult_min": 10.0},
    {"name": "Dr. B. Medicine", "department": "Medicine", "status": "available",
     "avg_consult_min": 12.0},
]


def rules_path() -> Path:
    import os

    return Path(os.getenv("MEDQUEUE_RULES_PATH", Path(__file__).parents[2] / "docs"
               / "red_flag_rules.yaml"))


def seed_users() -> int:
    """Create one clearly synthetic dev user per role; never overwrite passwords."""
    Base.metadata.create_all(engine)
    created = 0
    with SessionLocal.begin() as session:
        for item in DEV_USERS:
            assert item["role"] in VALID_ROLES
            if session.query(User).filter_by(username=item["username"]).first():
                continue
            session.add(
                User(
                    username=item["username"],
                    password_hash=hash_password(DEV_PASSWORD),
                    role=item["role"],
                )
            )
            created += 1
    return created


def seed_doctors() -> int:
    Base.metadata.create_all(engine)
    created = 0
    with SessionLocal.begin() as session:
        for item in DEMO_DOCTORS:
            if session.query(Doctor).filter_by(name=item["name"]).first():
                continue
            session.add(Doctor(**item))
            created += 1
    return created


def seed_demo_data() -> int:
    """Insert demo rows once; leave all existing records untouched."""
    Base.metadata.create_all(engine)
    rules = load_rules(rules_path())
    created = 0
    with SessionLocal.begin() as session:
        for item in DEMO_PATIENTS:
            if session.query(Patient).filter_by(name=item["name"]).first():
                continue
            patient = Patient(name=item["name"], date_of_birth=item["date_of_birth"])
            session.add(patient)
            session.flush()
            visit = Visit(
                patient_id=patient.id,
                complaint=item["complaint"],
                symptoms=item["symptoms"],
                registered_at=datetime.now(UTC) - timedelta(minutes=item["wait_min"]),
            )
            session.add(visit)
            session.flush()
            if item["vitals"]:
                session.add(Vital(visit_id=visit.id, values=item["vitals"]))
                session.flush()
            result = stub_triage(set(visit.symptoms), item["vitals"], None, rules)
            visit.triage_level = result["level"]
            visit.red_flag = result["red_flag"]
            visit.factors = result["factors"]
            visit.triage_source = result["source"]
            session.add(
                AuditEvent(
                    visit_id=visit.id,
                    actor="demo_seed",
                    action="demo_registered",
                    detail={},
                )
            )
            created += 1
    return created


if __name__ == "__main__":
    users = seed_users()
    doctors = seed_doctors()
    demos = seed_demo_data()
    print(f"Created {users} dev user(s), {doctors} doctor(s), "
          f"{demos} synthetic demo patient record(s).")
