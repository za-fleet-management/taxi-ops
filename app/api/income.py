from datetime import date

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_owner
from app.database import get_db
from app.models.base import gen_uuid
from app.models.income import DailyIncome
from app.models.route import Route, RouteAssignment
from app.models.taxi import Taxi
from app.models.user import User
from app.schemas.income import IncomeCreate, IncomeResponse

router = APIRouter(prefix="/income", tags=["income"])


@router.get("", response_model=list[IncomeResponse])
def list_income(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    taxi_id: str | None = None,
    driver_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    q = db.query(DailyIncome).filter(
        DailyIncome.organisation_id == user.organisation_id
    )
    if start_date:
        q = q.filter(DailyIncome.date >= start_date)
    if end_date:
        q = q.filter(DailyIncome.date <= end_date)
    if taxi_id:
        q = q.filter(DailyIncome.taxi_id == taxi_id)
    if driver_id:
        q = q.filter(DailyIncome.driver_id == driver_id)
    return q.all()


@router.post("", response_model=IncomeResponse)
def create_income(
    body: IncomeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.id:
        existing = db.query(DailyIncome).filter(DailyIncome.id == body.id).first()
        if existing:
            return existing

    route_id = body.route_id

    if not route_id:
        taxi = db.query(Taxi).filter(
            Taxi.id == body.taxi_id,
            Taxi.organisation_id == user.organisation_id,
        ).first()
        if taxi and taxi.assigned_route_id:
            route_id = taxi.assigned_route_id

    income_id = body.id or gen_uuid()
    income = DailyIncome(
        id=income_id,
        organisation_id=user.organisation_id,
        taxi_id=body.taxi_id,
        driver_id=body.driver_id,
        date=body.date,
        total_cash=body.total_cash,
        notes=body.notes,
        captured_by=user.id,
    )
    db.add(income)

    if route_id:
        route = db.query(Route).filter(
            Route.id == route_id,
            Route.organisation_id == user.organisation_id,
        ).first()
        if route:
            assignment = RouteAssignment(
                id=gen_uuid(),
                organisation_id=user.organisation_id,
                daily_income_id=income_id,
                route_id=route_id,
            )
            db.add(assignment)

    db.commit()
    db.refresh(income)
    return JSONResponse(
        content=jsonable_encoder(income),
        status_code=status.HTTP_201_CREATED,
    )
