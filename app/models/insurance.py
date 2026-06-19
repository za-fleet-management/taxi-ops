from datetime import date, datetime, timezone

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, gen_uuid


class Insurance(Base):
    __tablename__ = "insurance"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    taxi_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("taxis.id"), nullable=False
    )
    insurer: Mapped[str] = mapped_column(String(255))
    policy_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monthly_premium_cents: Mapped[int] = mapped_column(nullable=False)
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
