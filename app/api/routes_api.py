from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_owner
from app.database import get_db
from app.models.base import gen_uuid
from app.models.route import Route
from app.models.user import User
from app.schemas.route import RouteCreate, RouteResponse

router = APIRouter(prefix="/routes", tags=["routes"])


@router.post("", response_model=RouteResponse, status_code=status.HTTP_201_CREATED)
def create_route(
    body: RouteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    route = Route(
        id=gen_uuid(),
        organisation_id=user.organisation_id,
        name=body.name,
        distance_km=body.distance_km,
    )
    db.add(route)
    db.commit()
    db.refresh(route)
    return route


@router.get("", response_model=list[RouteResponse])
def list_routes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return db.query(Route).filter(Route.organisation_id == user.organisation_id).all()
