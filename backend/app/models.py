"""SQLAlchemy records used by the MedQueue prototype."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    date_of_birth: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    complaint: Mapped[str] = mapped_column(Text)
    symptoms: Mapped[list[str]] = mapped_column(JSON, default=list)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="waiting", index=True)
    triage_level: Mapped[int] = mapped_column(Integer, default=4)
    red_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    factors: Mapped[list[str]] = mapped_column(JSON, default=list)
    triage_source: Mapped[str] = mapped_column(String(20), default="stub")
    override_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_by: Mapped[str | None] = mapped_column(String(80), nullable=True)


class Vital(Base):
    __tablename__ = "vitals"

    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), index=True)
    values: Mapped[dict[str, float]] = mapped_column(JSON)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), index=True)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
