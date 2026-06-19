from datetime import date, datetime, timezone

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, gen_uuid


class OrganisationSubscription(Base):
    __tablename__ = "organisation_subscriptions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), unique=True, nullable=False, index=True
    )
    plan_months: Mapped[int] = mapped_column(nullable=False)
    price_per_taxi_cents: Mapped[int] = mapped_column(nullable=False)
    taxi_count: Mapped[int] = mapped_column(nullable=False)
    total_amount_cents: Mapped[int] = mapped_column(nullable=False)
    period_start: Mapped[date] = mapped_column(nullable=False)
    period_end: Mapped[date] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class SubscriptionPayment(Base):
    __tablename__ = "subscription_payments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    subscription_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisation_subscriptions.id"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(nullable=False)
    reference: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_date: Mapped[date] = mapped_column(nullable=False)
    bank_confirmed: Mapped[bool] = mapped_column(default=False)
    bank_confirmed_by: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True
    )
    bank_confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    confirmed: Mapped[bool] = mapped_column(default=False)
    confirmed_by: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
