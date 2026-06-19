from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_owner
from app.database import get_db
from app.models.depot import Depot
from app.models.user import User
from app.schemas.depot import DepotCreate, DepotResponse, DepotUpdate

router = APIRouter(prefix="/depots", tags=["depots"])


@router.get("", response_model=list[DepotResponse])
def list_depots(
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    return (
        db.query(Depot)
        .filter(Depot.organisation_id == user.organisation_id)
        .order_by(Depot.name)
        .all()
    )


@router.post("", response_model=DepotResponse, status_code=status.HTTP_201_CREATED)
def create_depot(
    body: DepotCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    existing = (
        db.query(Depot)
        .filter(
            Depot.organisation_id == user.organisation_id,
            Depot.name == body.name,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A depot with this name already exists",
        )

    depot = Depot(
        organisation_id=user.organisation_id,
        name=body.name,
        depot_type=body.depot_type,
        address=body.address,
    )
    db.add(depot)
    db.commit()
    db.refresh(depot)
    return depot


@router.patch("/{depot_id}", response_model=DepotResponse)
def update_depot(
    depot_id: str,
    body: DepotUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    depot = (
        db.query(Depot)
        .filter(
            Depot.id == depot_id,
            Depot.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not depot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if body.name is not None:
        name_check = (
            db.query(Depot)
            .filter(
                Depot.organisation_id == user.organisation_id,
                Depot.name == body.name,
                Depot.id != depot_id,
            )
            .first()
        )
        if name_check:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A depot with this name already exists",
            )
        depot.name = body.name
    if body.depot_type is not None:
        depot.depot_type = body.depot_type
    if body.address is not None:
        depot.address = body.address
    db.commit()
    db.refresh(depot)
    return depot
