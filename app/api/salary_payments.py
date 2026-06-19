from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_accountant_or_above, require_owner
from app.database import get_db
from app.models.driver import Driver
from app.models.employee import Employee
from app.models.salary_payment import SalaryPayment
from app.models.user import User
from app.schemas.salary_payment import (
    SalaryPaymentCreate,
    SalaryPaymentResponse,
    SalaryPaymentWithEmployee,
)

router = APIRouter(prefix="/salary-payments", tags=["salary-payments"])


@router.post("", response_model=SalaryPaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    body: SalaryPaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    emp = (
        db.query(Employee)
        .filter(
            Employee.id == body.employee_id,
            Employee.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    payment = SalaryPayment(
        organisation_id=user.organisation_id,
        employee_id=body.employee_id,
        amount_cents=body.amount_cents,
        payment_date=body.payment_date,
        payment_method=body.payment_method,
        reference=body.reference,
        notes=body.notes,
        created_by=user.id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


@router.get("", response_model=list[SalaryPaymentWithEmployee])
def list_payments(
    employee_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_accountant_or_above),
):
    q = (
        db.query(
            SalaryPayment,
            Driver.name.label("driver_name"),
        )
        .join(Employee, Employee.id == SalaryPayment.employee_id)
        .join(Driver, Driver.id == Employee.driver_id)
        .filter(SalaryPayment.organisation_id == user.organisation_id)
    )
    if employee_id:
        q = q.filter(SalaryPayment.employee_id == employee_id)
    if start_date:
        q = q.filter(SalaryPayment.payment_date >= start_date)
    if end_date:
        q = q.filter(SalaryPayment.payment_date <= end_date)

    rows = q.order_by(SalaryPayment.payment_date.desc()).all()

    return [
        SalaryPaymentWithEmployee(
            id=p.id,
            organisation_id=p.organisation_id,
            employee_id=p.employee_id,
            driver_name=driver_name,
            amount_cents=p.amount_cents,
            payment_date=p.payment_date,
            payment_method=p.payment_method,
            reference=p.reference,
            notes=p.notes,
            created_by=p.created_by,
            created_at=p.created_at,
        )
        for p, driver_name in rows
    ]
