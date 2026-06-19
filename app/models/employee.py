from datetime import date, datetime, timezone

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, gen_uuid


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("organisation_id", "driver_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    driver_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("drivers.id"), nullable=False
    )
    remuneration_package_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("remuneration_packages.id"), nullable=True
    )
    depot_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("depots.id"), nullable=True
    )
    employment_status: Mapped[str] = mapped_column(String(20), default="active")
    hire_date: Mapped[date] = mapped_column(nullable=False)
    termination_date: Mapped[date | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
