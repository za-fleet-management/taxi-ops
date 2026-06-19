import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, gen_uuid


class SparePartPurchase(Base):
    __tablename__ = "spare_part_purchases"
    __table_args__ = (
        Index("ix_spare_parts_org_taxi_date", "organisation_id", "taxi_id", "date"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    depot_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("depots.id"), nullable=False
    )
    taxi_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("taxis.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(500))
    cost_total_cents: Mapped[int] = mapped_column(nullable=False)
    date: Mapped[datetime.date] = mapped_column(nullable=False)
    created_by: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.timezone.utc))
