from datetime import date, datetime, timezone

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, gen_uuid


class DailyIncome(Base):
    __tablename__ = "daily_income"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    taxi_id: Mapped[str] = mapped_column(String(32), ForeignKey("taxis.id"), nullable=False)
    driver_id: Mapped[str] = mapped_column(String(32), ForeignKey("drivers.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total_cash: Mapped[int] = mapped_column(nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    captured_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("organisation_id", "taxi_id", "date"),
    )
