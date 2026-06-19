from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, gen_uuid


class UserRole(str, Enum):
    SUPERADMIN = "superadmin"
    OWNER = "owner"
    MANAGER = "manager"
    DISPATCHER = "dispatcher"
    ACCOUNTANT = "accountant"
    VIEWER = "viewer"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(15))
    status: Mapped[str] = mapped_column(String(10), default=UserStatus.ACTIVE.value)
    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    organisation = relationship("Organisation")
