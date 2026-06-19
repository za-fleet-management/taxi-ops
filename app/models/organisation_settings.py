from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, gen_uuid


class OrganisationSettings(Base):
    __tablename__ = "organisation_settings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), unique=True, nullable=False
    )
    vat_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vat_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    financial_year_end: Mapped[date] = mapped_column(
        Date, default=lambda: date(date.today().year, 2, 28), nullable=False
    )
    default_currency: Mapped[str] = mapped_column(String(3), default="ZAR", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
