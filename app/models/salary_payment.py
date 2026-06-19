from datetime import date, datetime, timezone

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, gen_uuid


class SalaryPayment(Base):
    __tablename__ = "salary_payments"
    __table_args__ = (
        Index("ix_salary_payments_org_employee_date", "organisation_id", "employee_id", "payment_date"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    organisation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organisations.id"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("employees.id"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(nullable=False)
    payment_date: Mapped[date] = mapped_column(nullable=False)
    payment_method: Mapped[str] = mapped_column(String(20), default="cash")
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
