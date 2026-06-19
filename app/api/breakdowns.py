from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_owner
from app.database import get_db
from app.models.base import gen_uuid
from app.models.breakdown import Breakdown
from app.models.taxi import Taxi
from app.models.user import User
from app.schemas.breakdown import BreakdownClose, BreakdownCreate, BreakdownResponse

router = APIRouter(prefix="/breakdowns", tags=["breakdowns"])


@router.get("", response_model=list[BreakdownResponse])
def list_breakdowns(
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    return (
        db.query(Breakdown)
        .filter(Breakdown.organisation_id == user.organisation_id)
        .all()
    )


@router.post("", response_model=BreakdownResponse)
def create_breakdown(
    body: BreakdownCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.id:
        existing = db.query(Breakdown).filter(Breakdown.id == body.id).first()
        if existing:
            return existing

    taxi = (
        db.query(Taxi)
        .filter(
            Taxi.id == body.taxi_id,
            Taxi.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not taxi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taxi not found")

    breakdown = Breakdown(
        id=body.id or gen_uuid(),
        organisation_id=user.organisation_id,
        taxi_id=body.taxi_id,
        start_time=body.start_time,
        reason=body.reason,
        captured_by=user.id,
    )
    db.add(breakdown)

    taxi.status = "breakdown"
    db.commit()
    db.refresh(breakdown)
    return JSONResponse(
        content=jsonable_encoder(breakdown),
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/{breakdown_id}/close", response_model=BreakdownResponse)
def close_breakdown(
    breakdown_id: str,
    body: BreakdownClose,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    breakdown = (
        db.query(Breakdown)
        .filter(
            Breakdown.id == breakdown_id,
            Breakdown.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not breakdown:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if breakdown.end_time is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Breakdown already closed"
        )

    breakdown.end_time = body.end_time
    breakdown.cost_total = body.cost_total
    breakdown.parts_used = body.parts_used

    taxi = (
        db.query(Taxi)
        .filter(
            Taxi.id == breakdown.taxi_id,
            Taxi.organisation_id == user.organisation_id,
        )
        .first()
    )
    if taxi:
        taxi.status = "active"

    db.commit()
    db.refresh(breakdown)
    return breakdown
