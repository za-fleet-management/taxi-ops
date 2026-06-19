from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, gen_uuid


class Breakdown(Base):
    __tablename__ = "breakdowns"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    taxi_id: Mapped[str] = mapped_column(String(32), ForeignKey("taxis.id"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cost_total: Mapped[int | None] = mapped_column(nullable=True)
    parts_used: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    captured_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
