from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, gen_uuid


class Depot(Base):
    __tablename__ = "depots"
    __table_args__ = (
        UniqueConstraint("organisation_id", "name"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    depot_type: Mapped[str] = mapped_column(String(20), default="mixed")
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
