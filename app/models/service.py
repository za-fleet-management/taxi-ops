from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, gen_uuid


class ServiceType(Base):
    __tablename__ = "service_types"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    interval_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reminder_days_before: Mapped[int] = mapped_column(Integer, default=7)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )


class TaxiServiceSchedule(Base):
    __tablename__ = "taxi_service_schedules"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    taxi_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("taxis.id"), nullable=False
    )
    service_type_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("service_types.id"), nullable=False
    )
    last_service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_service_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_due_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    taxi = relationship("Taxi", foreign_keys=[taxi_id])
    service_type = relationship("ServiceType", foreign_keys=[service_type_id])


class ServiceRecord(Base):
    __tablename__ = "service_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    taxi_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("taxis.id"), nullable=False
    )
    service_type_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("service_types.id"), nullable=False
    )
    schedule_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("taxi_service_schedules.id"), nullable=True
    )
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    odometer_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_cents: Mapped[int] = mapped_column(nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_by: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    taxi = relationship("Taxi", foreign_keys=[taxi_id])
    service_type = relationship("ServiceType", foreign_keys=[service_type_id])
