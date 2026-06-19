from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_dispatcher_or_above, require_owner
from app.database import get_db
from app.models.taxi import Taxi
from app.models.user import User
from app.schemas.taxi import TaxiCreate, TaxiResponse, TaxiUpdate

router = APIRouter(prefix="/taxis", tags=["taxis"])


@router.get("", response_model=list[TaxiResponse])
def list_taxis(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(Taxi)
        .filter(Taxi.organisation_id == user.organisation_id)
        .all()
    )


@router.post("", response_model=TaxiResponse, status_code=status.HTTP_201_CREATED)
def create_taxi(
    body: TaxiCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_dispatcher_or_above),
):
    existing = (
        db.query(Taxi)
        .filter(
            Taxi.organisation_id == user.organisation_id,
            Taxi.registration_number == body.registration_number,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Registration number already exists")

    taxi = Taxi(
        organisation_id=user.organisation_id,
        registration_number=body.registration_number,
        model=body.model,
        status=body.status,
        assigned_route_id=body.assigned_route_id,
    )
    db.add(taxi)
    db.commit()
    db.refresh(taxi)
    return taxi


@router.patch("/{taxi_id}", response_model=TaxiResponse)
def update_taxi(
    taxi_id: str,
    body: TaxiUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_dispatcher_or_above),
):
    taxi = (
        db.query(Taxi)
        .filter(
            Taxi.id == taxi_id,
            Taxi.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not taxi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if body.registration_number is not None:
        taxi.registration_number = body.registration_number
    if body.model is not None:
        taxi.model = body.model
    if body.status is not None:
        taxi.status = body.status
    if body.assigned_route_id is not None or "assigned_route_id" in body.model_fields_set:
        taxi.assigned_route_id = body.assigned_route_id
    db.commit()
    db.refresh(taxi)
    return taxi
