from datetime import date, datetime, timezone

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, gen_uuid


class TaxiLoan(Base):
    __tablename__ = "taxi_loans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    taxi_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("taxis.id"), nullable=False
    )
    lender: Mapped[str] = mapped_column(String(255))
    total_amount_cents: Mapped[int] = mapped_column(nullable=False)
    remaining_balance_cents: Mapped[int] = mapped_column(nullable=False)
    monthly_instalment_cents: Mapped[int] = mapped_column(nullable=False)
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class LoanPayment(Base):
    __tablename__ = "loan_payments"
    __table_args__ = (
        Index("ix_loan_payments_org_loan_date", "organisation_id", "loan_id", "payment_date"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    loan_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("taxi_loans.id"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(nullable=False)
    payment_date: Mapped[date] = mapped_column(nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
