from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_owner
from app.database import get_db
from app.models.depot import Depot
from app.models.spare_part import SparePartPurchase
from app.models.taxi import Taxi
from app.models.user import User
from app.schemas.spare_part import (
    SparePartPurchaseCreate,
    SparePartPurchaseResponse,
    SparePartPurchaseWithDetails,
)

router = APIRouter(prefix="/spare-parts", tags=["spare-parts"])


@router.get("", response_model=list[SparePartPurchaseWithDetails])
def list_spare_parts(
    depot_id: str | None = None,
    taxi_id: str | None = None,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    q = (
        db.query(
            SparePartPurchase,
            Depot.name.label("depot_name"),
            Taxi.registration_number.label("taxi_registration"),
        )
        .join(Depot, Depot.id == SparePartPurchase.depot_id)
        .outerjoin(Taxi, Taxi.id == SparePartPurchase.taxi_id)
        .filter(SparePartPurchase.organisation_id == user.organisation_id)
    )
    if depot_id:
        q = q.filter(SparePartPurchase.depot_id == depot_id)
    if taxi_id:
        q = q.filter(SparePartPurchase.taxi_id == taxi_id)
    if start_date:
        q = q.filter(SparePartPurchase.date >= start_date)
    if end_date:
        q = q.filter(SparePartPurchase.date <= end_date)

    rows = q.order_by(SparePartPurchase.date.desc()).all()

    return [
        SparePartPurchaseWithDetails(
            id=p.id,
            organisation_id=p.organisation_id,
            depot_id=p.depot_id,
            depot_name=depot_name,
            taxi_id=p.taxi_id,
            taxi_registration=taxi_registration,
            description=p.description,
            cost_total_cents=p.cost_total_cents,
            date=p.date,
            created_by=p.created_by,
            created_at=p.created_at,
        )
        for p, depot_name, taxi_registration in rows
    ]


@router.post("", response_model=SparePartPurchaseResponse, status_code=status.HTTP_201_CREATED)
def create_spare_part(
    body: SparePartPurchaseCreate,
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

    purchase = SparePartPurchase(
        organisation_id=user.organisation_id,
        depot_id=body.depot_id,
        taxi_id=body.taxi_id,
        description=body.description,
        cost_total_cents=body.cost_total_cents,
        date=body.date,
        created_by=user.id,
    )
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    return purchase
