from datetime import date, datetime, timezone

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, gen_uuid


class Fuel(Base):
    __tablename__ = "fuel"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    taxi_id: Mapped[str] = mapped_column(String(32), ForeignKey("taxis.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    litres: Mapped[float] = mapped_column(nullable=False)
    cost_total: Mapped[int] = mapped_column(nullable=False)
    odometer_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    captured_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
