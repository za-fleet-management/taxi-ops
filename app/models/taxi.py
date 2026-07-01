from datetime import date, datetime, timezone

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, gen_uuid


class Taxi(Base):
    __tablename__ = "taxis"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    registration_number: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="active")
    assigned_route_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("routes.id"), nullable=True
    )
    license_disk_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    license_disk_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    route = relationship("Route", foreign_keys=[assigned_route_id])

    __table_args__ = (
        UniqueConstraint("organisation_id", "registration_number"),
    )
