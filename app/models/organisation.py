from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, gen_uuid


class Organisation(Base):
    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255))
    region: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
