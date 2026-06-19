from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_owner
from app.database import get_db
from app.models.taxi import Taxi
from app.models.taxi_loan import LoanPayment, TaxiLoan
from app.models.user import User
from app.schemas.taxi_loan import (
    LoanPaymentCreate,
    LoanPaymentResponse,
    TaxiLoanCreate,
    TaxiLoanResponse,
    TaxiLoanUpdate,
)

router = APIRouter(prefix="/taxi-loans", tags=["taxi-loans"])


@router.get("", response_model=list[TaxiLoanResponse])
def list_loans(
    taxi_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    q = db.query(TaxiLoan).filter(TaxiLoan.organisation_id == user.organisation_id)
    if taxi_id:
        q = q.filter(TaxiLoan.taxi_id == taxi_id)
    return q.order_by(TaxiLoan.created_at.desc()).all()


@router.post("", response_model=TaxiLoanResponse, status_code=status.HTTP_201_CREATED)
def create_loan(
    body: TaxiLoanCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    taxi = db.query(Taxi).filter(
        Taxi.id == body.taxi_id,
        Taxi.organisation_id == user.organisation_id,
    ).first()
    if not taxi:
        raise HTTPException(status_code=404, detail="Taxi not found")

    loan = TaxiLoan(
        organisation_id=user.organisation_id,
        taxi_id=body.taxi_id,
        lender=body.lender,
        total_amount_cents=body.total_amount_cents,
        remaining_balance_cents=body.remaining_balance_cents,
        monthly_instalment_cents=body.monthly_instalment_cents,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    db.add(loan)
    db.commit()
    db.refresh(loan)
    return loan


@router.patch("/{loan_id}", response_model=TaxiLoanResponse)
def update_loan(
    loan_id: str,
    body: TaxiLoanUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    loan = (
        db.query(TaxiLoan)
        .filter(
            TaxiLoan.id == loan_id,
            TaxiLoan.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if body.lender is not None:
        loan.lender = body.lender
    if body.remaining_balance_cents is not None:
        loan.remaining_balance_cents = body.remaining_balance_cents
    if body.monthly_instalment_cents is not None:
        loan.monthly_instalment_cents = body.monthly_instalment_cents
    if body.end_date is not None:
        loan.end_date = body.end_date
    db.commit()
    db.refresh(loan)
    return loan


@router.get("/{loan_id}/payments", response_model=list[LoanPaymentResponse])
def list_loan_payments(
    loan_id: str,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    loan = (
        db.query(TaxiLoan)
        .filter(
            TaxiLoan.id == loan_id,
            TaxiLoan.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    q = db.query(LoanPayment).filter(
        LoanPayment.organisation_id == user.organisation_id,
        LoanPayment.loan_id == loan_id,
    )
    if start_date:
        q = q.filter(LoanPayment.payment_date >= start_date)
    if end_date:
        q = q.filter(LoanPayment.payment_date <= end_date)
    return q.order_by(LoanPayment.payment_date.desc()).all()


@router.post("/{loan_id}/payments", response_model=LoanPaymentResponse, status_code=status.HTTP_201_CREATED)
def create_loan_payment(
    loan_id: str,
    body: LoanPaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    loan = (
        db.query(TaxiLoan)
        .filter(
            TaxiLoan.id == loan_id,
            TaxiLoan.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    payment = LoanPayment(
        organisation_id=user.organisation_id,
        loan_id=loan_id,
        amount_cents=body.amount_cents,
        payment_date=body.payment_date,
        reference=body.reference,
        created_by=user.id,
    )
    db.add(payment)

    loan.remaining_balance_cents = max(0, loan.remaining_balance_cents - body.amount_cents)

    db.commit()
    db.refresh(payment)
    return payment
