from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_owner
from app.database import get_db
from app.models.depot import Depot
from app.models.mechanic_payment import MechanicPayment
from app.models.taxi import Taxi
from app.models.user import User
from app.schemas.mechanic_payment import (
    MechanicPaymentCreate,
    MechanicPaymentResponse,
    MechanicPaymentWithDetails,
)

router = APIRouter(prefix="/mechanic-payments", tags=["mechanic-payments"])


@router.get("", response_model=list[MechanicPaymentWithDetails])
def list_mechanic_payments(
    depot_id: str | None = None,
    taxi_id: str | None = None,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    q = (
        db.query(
            MechanicPayment,
            Depot.name.label("depot_name"),
            Taxi.registration_number.label("taxi_registration"),
        )
        .join(Depot, Depot.id == MechanicPayment.depot_id)
        .outerjoin(Taxi, Taxi.id == MechanicPayment.taxi_id)
        .filter(MechanicPayment.organisation_id == user.organisation_id)
    )
    if depot_id:
        q = q.filter(MechanicPayment.depot_id == depot_id)
    if taxi_id:
        q = q.filter(MechanicPayment.taxi_id == taxi_id)
    if start_date:
        q = q.filter(MechanicPayment.payment_date >= start_date)
    if end_date:
        q = q.filter(MechanicPayment.payment_date <= end_date)

    rows = q.order_by(MechanicPayment.payment_date.desc()).all()

    return [
        MechanicPaymentWithDetails(
            id=p.id,
            organisation_id=p.organisation_id,
            depot_id=p.depot_id,
            depot_name=depot_name,
            taxi_id=p.taxi_id,
            taxi_registration=taxi_registration,
            mechanic_name=p.mechanic_name,
            description=p.description,
            amount_cents=p.amount_cents,
            payment_date=p.payment_date,
            payment_method=p.payment_method,
            created_by=p.created_by,
            created_at=p.created_at,
        )
        for p, depot_name, taxi_registration in rows
    ]


@router.post("", response_model=MechanicPaymentResponse, status_code=status.HTTP_201_CREATED)
def create_mechanic_payment(
    body: MechanicPaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    depot = db.query(Depot).filter(
        Depot.id == body.depot_id,
        Depot.organisation_id == user.organisation_id,
    ).first()
    if not depot:
        raise HTTPException(status_code=404, detail="Depot not found")

    if body.taxi_id:
        taxi = db.query(Taxi).filter(
            Taxi.id == body.taxi_id,
            Taxi.organisation_id == user.organisation_id,
        ).first()
        if not taxi:
            raise HTTPException(status_code=404, detail="Taxi not found")

    payment = MechanicPayment(
        organisation_id=user.organisation_id,
        depot_id=body.depot_id,
        taxi_id=body.taxi_id,
        mechanic_name=body.mechanic_name,
        description=body.description,
        amount_cents=body.amount_cents,
        payment_date=body.payment_date,
        payment_method=body.payment_method,
        created_by=user.id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment
