from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_owner
from app.database import get_db
from app.models.insurance import Insurance
from app.models.taxi import Taxi
from app.models.user import User
from app.schemas.insurance import (
    InsuranceCreate,
    InsuranceResponse,
    InsuranceUpdate,
    InsuranceWithTaxi,
)

router = APIRouter(prefix="/insurance", tags=["insurance"])


@router.get("", response_model=list[InsuranceWithTaxi])
def list_insurance(
    taxi_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    q = (
        db.query(
            Insurance,
            Taxi.registration_number.label("registration_number"),
        )
        .join(Taxi, Taxi.id == Insurance.taxi_id)
        .filter(Insurance.organisation_id == user.organisation_id)
    )
    if taxi_id:
        q = q.filter(Insurance.taxi_id == taxi_id)
    rows = q.order_by(Insurance.created_at.desc()).all()

    return [
        InsuranceWithTaxi(
            id=i.id,
            organisation_id=i.organisation_id,
            taxi_id=i.taxi_id,
            registration_number=registration_number,
            insurer=i.insurer,
            policy_number=i.policy_number,
            monthly_premium_cents=i.monthly_premium_cents,
            start_date=i.start_date,
            end_date=i.end_date,
            created_at=i.created_at,
        )
        for i, registration_number in rows
    ]


@router.post("", response_model=InsuranceResponse, status_code=status.HTTP_201_CREATED)
def create_insurance(
    body: InsuranceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    taxi = db.query(Taxi).filter(
        Taxi.id == body.taxi_id,
        Taxi.organisation_id == user.organisation_id,
    ).first()
    if not taxi:
        raise HTTPException(status_code=404, detail="Taxi not found")

    insurance = Insurance(
        organisation_id=user.organisation_id,
        taxi_id=body.taxi_id,
        insurer=body.insurer,
        policy_number=body.policy_number,
        monthly_premium_cents=body.monthly_premium_cents,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    db.add(insurance)
    db.commit()
    db.refresh(insurance)
    return insurance


@router.patch("/{insurance_id}", response_model=InsuranceResponse)
def update_insurance(
    insurance_id: str,
    body: InsuranceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    ins = (
        db.query(Insurance)
        .filter(
            Insurance.id == insurance_id,
            Insurance.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not ins:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if body.insurer is not None:
        ins.insurer = body.insurer
    if body.policy_number is not None:
        ins.policy_number = body.policy_number
    if body.monthly_premium_cents is not None:
        ins.monthly_premium_cents = body.monthly_premium_cents
    if body.end_date is not None:
        ins.end_date = body.end_date
    db.commit()
    db.refresh(ins)
    return ins
