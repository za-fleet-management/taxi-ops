from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_owner
from app.database import get_db
from app.models.base import gen_uuid
from app.models.fuel import Fuel
from app.models.taxi import Taxi
from app.models.user import User
from app.schemas.fuel import FuelCreate, FuelResponse

router = APIRouter(prefix="/fuel", tags=["fuel"])


@router.post("", response_model=FuelResponse, status_code=status.HTTP_201_CREATED)
def create_fuel(
    body: FuelCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    taxi = db.query(Taxi).filter(
        Taxi.id == body.taxi_id,
        Taxi.organisation_id == user.organisation_id,
    ).first()
    if not taxi:
        raise HTTPException(status_code=404, detail="Taxi not found")

    fuel = Fuel(
        id=gen_uuid(),
        organisation_id=user.organisation_id,
        taxi_id=body.taxi_id,
        date=body.date,
        litres=body.litres,
        cost_total=body.cost_total,
        odometer_km=body.odometer_km,
        captured_by=user.id,
    )
    db.add(fuel)
    db.commit()
    db.refresh(fuel)
    return fuel


@router.get("", response_model=list[FuelResponse])
def list_fuel(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    taxi_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    q = db.query(Fuel).filter(Fuel.organisation_id == user.organisation_id)
    if start_date:
        q = q.filter(Fuel.date >= start_date)
    if end_date:
        q = q.filter(Fuel.date <= end_date)
    if taxi_id:
        q = q.filter(Fuel.taxi_id == taxi_id)
    return q.order_by(Fuel.date.desc()).all()
