from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, gen_uuid


class InviteToken(Base):
    __tablename__ = "invite_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(15), default="manager")
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
