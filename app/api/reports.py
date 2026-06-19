from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, sql
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_owner
from app.database import get_db
from app.models.breakdown import Breakdown
from app.models.driver import Driver
from app.models.fuel import Fuel
from app.models.income import DailyIncome
from app.models.insurance import Insurance
from app.models.mechanic_payment import MechanicPayment
from app.models.route import Route, RouteAssignment
from app.models.spare_part import SparePartPurchase
from app.models.taxi import Taxi
from app.models.taxi_loan import LoanPayment, TaxiLoan
from app.models.user import User
from app.schemas.reports import (
    CostOfOperationsItem,
    CostOfOperationsResponse,
    DowntimeCostItem,
    DowntimeCostResponse,
    DriverPerformanceItem,
    DriverPerformanceResponse,
    IncomeSummaryItem,
    IncomeSummaryResponse,
    RouteProfitabilityItem,
    RouteProfitabilityResponse,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/income-summary", response_model=IncomeSummaryResponse)
def income_summary(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    taxi_id: str | None = None,
    driver_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    q = db.query(
        DailyIncome.date,
        func.sum(DailyIncome.total_cash).label("total_cash"),
        func.count(DailyIncome.id).label("entry_count"),
    ).filter(DailyIncome.organisation_id == user.organisation_id)

    if start_date:
        q = q.filter(DailyIncome.date >= start_date)
    if end_date:
        q = q.filter(DailyIncome.date <= end_date)
    if taxi_id:
        q = q.filter(DailyIncome.taxi_id == taxi_id)
    if driver_id:
        q = q.filter(DailyIncome.driver_id == driver_id)

    q = q.group_by(DailyIncome.date).order_by(DailyIncome.date)

    rows = q.all()
    items = [IncomeSummaryItem(date=r.date, total_cash=r.total_cash, entry_count=r.entry_count) for r in rows]
    return IncomeSummaryResponse(items=items, grand_total=sum(r.total_cash for r in rows))


@router.get("/driver-performance", response_model=DriverPerformanceResponse)
def driver_performance(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    driver_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    org_id = user.organisation_id
    income_q = db.query(
        DailyIncome.driver_id,
        func.sum(DailyIncome.total_cash).label("total_income"),
        func.count(DailyIncome.id).label("income_days"),
    ).filter(
        DailyIncome.organisation_id == org_id,
    )
    if start_date:
        income_q = income_q.filter(DailyIncome.date >= start_date)
    if end_date:
        income_q = income_q.filter(DailyIncome.date <= end_date)
    if driver_id:
        income_q = income_q.filter(DailyIncome.driver_id == driver_id)
    income_rows = {r.driver_id: r for r in income_q.group_by(DailyIncome.driver_id).all()}

    driver_q = db.query(Driver).filter(
        Driver.organisation_id == org_id,
        Driver.status == "active",
    )
    if driver_id:
        driver_q = driver_q.filter(Driver.id == driver_id)
    drivers = driver_q.all()

    # Determine the date range for idle day calculation
    if start_date is None:
        start_date = db.query(func.min(DailyIncome.date)).filter(
            DailyIncome.organisation_id == org_id
        ).scalar() or date.today()
    if end_date is None:
        end_date = date.today()
    total_calendar_days = (end_date - start_date).days + 1

    items = []
    for d in drivers:
        inc = income_rows.get(d.id)
        total_income = inc.total_income if inc else 0
        income_days = inc.income_days if inc else 0
        # Idle days: calendar days in range minus income days
        idle_days = max(0, total_calendar_days - income_days)
        items.append(
            DriverPerformanceItem(
                driver_id=d.id,
                driver_name=d.name,
                total_income_cents=total_income,
                income_days=income_days,
                idle_days=idle_days,
            )
        )

    return DriverPerformanceResponse(items=items)


@router.get("/downtime-cost", response_model=DowntimeCostResponse)
def downtime_cost(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    taxi_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    q = db.query(
        Breakdown.id,
        Breakdown.taxi_id,
        Taxi.registration_number,
        Breakdown.start_time,
        Breakdown.end_time,
        Breakdown.cost_total,
    ).join(Taxi, Breakdown.taxi_id == Taxi.id).filter(
        Breakdown.organisation_id == user.organisation_id,
    )
    if start_date:
        q = q.filter(Breakdown.start_time >= start_date)
    if end_date:
        q = q.filter(Breakdown.start_time <= end_date)
    if taxi_id:
        q = q.filter(Breakdown.taxi_id == taxi_id)
    q = q.order_by(Breakdown.start_time.desc())

    total_cost = 0
    items = []
    for row in q.all():
        cost = row.cost_total or 0
        total_cost += cost
        duration = timedelta()
        if row.end_time:
            duration = row.end_time - row.start_time
        items.append(
            DowntimeCostItem(
                breakdown_id=row.id,
                taxi_id=row.taxi_id,
                registration_number=row.registration_number,
                start_time=row.start_time,
                end_time=row.end_time,
                duration_hours=duration.total_seconds() / 3600,
                cost_total=row.cost_total,
            )
        )

    return DowntimeCostResponse(items=items, total_cost=total_cost)


def _days_in_month(d: date) -> int:
    """Return number of days in the month of the given date."""
    next_month = d.replace(day=28) + timedelta(days=4)
    return (next_month.replace(day=1) - timedelta(days=1)).day


def _calculate_insurance_cost(
    db: Session,
    org_id: str,
    taxi_id: str,
    start_date: date,
    end_date: date,
) -> int:
    """Calculate insurance cost for a taxi over a date range.

    For each day in the range, find the active insurance policy and add
    the pro-rated daily premium for that month.
    """
    policies = db.query(Insurance).filter(
        Insurance.organisation_id == org_id,
        Insurance.taxi_id == taxi_id,
        Insurance.start_date <= end_date,
    ).all()

    if not policies:
        return 0

    total = 0
    current = start_date
    while current <= end_date:
        day_premium = 0
        for policy in policies:
            if (
                policy.start_date <= current
                and (policy.end_date is None or policy.end_date >= current)
            ):
                daily = policy.monthly_premium_cents / _days_in_month(current)
                day_premium = max(day_premium, daily)
                break  # Only count the active policy (latest one wins)
        total += day_premium
        current += timedelta(days=1)

    return round(total)


@router.get("/cost-of-operations", response_model=CostOfOperationsResponse)
def cost_of_operations(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    taxi_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    org_id = user.organisation_id

    if start_date is None:
        start_date = db.query(func.min(DailyIncome.date)).filter(
            DailyIncome.organisation_id == org_id
        ).scalar() or date.today().replace(day=1)
    if end_date is None:
        end_date = date.today()

    income_q = db.query(
        Taxi.id.label("taxi_id"),
        Taxi.registration_number,
        func.coalesce(func.sum(DailyIncome.total_cash), 0).label("total_income"),
    ).outerjoin(
        DailyIncome,
        sql.and_(
            DailyIncome.taxi_id == Taxi.id,
            DailyIncome.date >= start_date if start_date else sql.true(),
            DailyIncome.date <= end_date if end_date else sql.true(),
        ),
    ).filter(
        Taxi.organisation_id == org_id,
    )
    if taxi_id:
        income_q = income_q.filter(Taxi.id == taxi_id)
    income_q = income_q.group_by(Taxi.id, Taxi.registration_number)
    income_rows = income_q.all()

    fuel_q = db.query(
        Fuel.taxi_id,
        func.coalesce(func.sum(Fuel.cost_total), 0).label("total_fuel"),
    ).filter(Fuel.organisation_id == org_id)
    if start_date:
        fuel_q = fuel_q.filter(Fuel.date >= start_date)
    if end_date:
        fuel_q = fuel_q.filter(Fuel.date <= end_date)
    if taxi_id:
        fuel_q = fuel_q.filter(Fuel.taxi_id == taxi_id)
    fuel_rows = {r.taxi_id: r.total_fuel for r in fuel_q.group_by(Fuel.taxi_id).all()}

    bd_q = db.query(
        Breakdown.taxi_id,
        func.coalesce(func.sum(Breakdown.cost_total), 0).label("total_breakdown"),
    ).filter(Breakdown.organisation_id == org_id)
    if start_date:
        bd_q = bd_q.filter(Breakdown.start_time >= start_date)
    if end_date:
        bd_q = bd_q.filter(Breakdown.start_time <= end_date)
    if taxi_id:
        bd_q = bd_q.filter(Breakdown.taxi_id == taxi_id)
    bd_rows = {r.taxi_id: r.total_breakdown for r in bd_q.group_by(Breakdown.taxi_id).all()}

    loan_q = db.query(
        LoanPayment.loan_id,
        func.coalesce(func.sum(LoanPayment.amount_cents), 0).label("total_loan_payments"),
    ).filter(LoanPayment.organisation_id == org_id)
    if start_date:
        loan_q = loan_q.filter(LoanPayment.payment_date >= start_date)
    if end_date:
        loan_q = loan_q.filter(LoanPayment.payment_date <= end_date)
    loan_rows = {r.loan_id: r.total_loan_payments for r in loan_q.group_by(LoanPayment.loan_id).all()}

    # Map loan_id to taxi_id
    loan_to_taxi = {
        l.id: l.taxi_id
        for l in db.query(TaxiLoan.id, TaxiLoan.taxi_id).filter(
            TaxiLoan.organisation_id == org_id
        ).all()
    }

    sp_q = db.query(
        SparePartPurchase.taxi_id,
        func.coalesce(func.sum(SparePartPurchase.cost_total_cents), 0).label("total_spare_parts"),
    ).filter(
        SparePartPurchase.organisation_id == org_id,
        SparePartPurchase.taxi_id.isnot(None),
    )
    if start_date:
        sp_q = sp_q.filter(SparePartPurchase.date >= start_date)
    if end_date:
        sp_q = sp_q.filter(SparePartPurchase.date <= end_date)
    if taxi_id:
        sp_q = sp_q.filter(SparePartPurchase.taxi_id == taxi_id)
    sp_rows = {r.taxi_id: r.total_spare_parts for r in sp_q.group_by(SparePartPurchase.taxi_id).all()}

    mp_q = db.query(
        MechanicPayment.taxi_id,
        func.coalesce(func.sum(MechanicPayment.amount_cents), 0).label("total_mechanic_payments"),
    ).filter(
        MechanicPayment.organisation_id == org_id,
        MechanicPayment.taxi_id.isnot(None),
    )
    if start_date:
        mp_q = mp_q.filter(MechanicPayment.payment_date >= start_date)
    if end_date:
        mp_q = mp_q.filter(MechanicPayment.payment_date <= end_date)
    if taxi_id:
        mp_q = mp_q.filter(MechanicPayment.taxi_id == taxi_id)
    mp_rows = {r.taxi_id: r.total_mechanic_payments for r in mp_q.group_by(MechanicPayment.taxi_id).all()}

    items = []
    for r in income_rows:
        fuel_cost = fuel_rows.get(r.taxi_id, 0)
        bd_cost = bd_rows.get(r.taxi_id, 0)

        loan_cost = 0
        for lid, tid in loan_to_taxi.items():
            if tid == r.taxi_id:
                loan_cost += loan_rows.get(lid, 0)

        insurance_cost = _calculate_insurance_cost(
            db, org_id, r.taxi_id, start_date, end_date
        )
        sp_cost = sp_rows.get(r.taxi_id, 0)
        mp_cost = mp_rows.get(r.taxi_id, 0)

        ops_cost = fuel_cost + bd_cost + insurance_cost + loan_cost + sp_cost + mp_cost
        items.append(
            CostOfOperationsItem(
                taxi_id=r.taxi_id,
                registration_number=r.registration_number,
                total_income=r.total_income,
                total_fuel_cost=fuel_cost,
                total_breakdown_cost=bd_cost,
                total_insurance_cost=insurance_cost,
                total_loan_payment_cost=loan_cost,
                total_spare_part_cost=sp_cost,
                total_mechanic_payment_cost=mp_cost,
                cost_of_operations=ops_cost,
                net_position=r.total_income - ops_cost,
            )
        )

    return CostOfOperationsResponse(items=items)


@router.get("/route-profitability", response_model=RouteProfitabilityResponse)
def route_profitability(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    route_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    org_id = user.organisation_id

    income_q = db.query(
        Route.id.label("route_id"),
        Route.name.label("route_name"),
        Route.distance_km,
        func.count(DailyIncome.id).label("income_count"),
        func.coalesce(func.sum(DailyIncome.total_cash), 0).label("total_income"),
    ).select_from(Route).join(
        RouteAssignment, RouteAssignment.route_id == Route.id,
    ).join(
        DailyIncome, DailyIncome.id == RouteAssignment.daily_income_id,
    ).filter(Route.organisation_id == org_id)
    if start_date:
        income_q = income_q.filter(DailyIncome.date >= start_date)
    if end_date:
        income_q = income_q.filter(DailyIncome.date <= end_date)
    if route_id:
        income_q = income_q.filter(Route.id == route_id)
    income_q = income_q.group_by(Route.id, Route.name, Route.distance_km)
    route_data = income_q.all()

    # For each route, compute allocated costs proportionally
    items = []
    for r in route_data:
        fuel_q = db.query(
            func.coalesce(func.sum(Fuel.cost_total), 0),
        ).filter(
            Fuel.organisation_id == org_id,
            Fuel.taxi_id.in_(
                db.query(DailyIncome.taxi_id).filter(
                    DailyIncome.id.in_(
                        db.query(RouteAssignment.daily_income_id).filter(
                            RouteAssignment.route_id == r.route_id,
                        )
                    )
                )
            ),
        )
        if start_date:
            fuel_q = fuel_q.filter(Fuel.date >= start_date)
        if end_date:
            fuel_q = fuel_q.filter(Fuel.date <= end_date)
        total_fuel_cost = fuel_q.scalar() or 0

        bd_q = db.query(
            func.coalesce(func.sum(Breakdown.cost_total), 0),
        ).filter(
            Breakdown.organisation_id == org_id,
            Breakdown.taxi_id.in_(
                db.query(DailyIncome.taxi_id).filter(
                    DailyIncome.id.in_(
                        db.query(RouteAssignment.daily_income_id).filter(
                            RouteAssignment.route_id == r.route_id,
                        )
                    )
                )
            ),
        )
        if start_date:
            bd_q = bd_q.filter(Breakdown.start_time >= start_date)
        if end_date:
            bd_q = bd_q.filter(Breakdown.start_time <= end_date)
        total_breakdown_cost = bd_q.scalar() or 0

        allocated_costs = total_fuel_cost + total_breakdown_cost
        items.append(
            RouteProfitabilityItem(
                route_id=r.route_id,
                route_name=r.route_name,
                distance_km=r.distance_km,
                income_count=r.income_count,
                total_income=r.total_income,
                allocated_fuel_cost=total_fuel_cost,
                allocated_breakdown_cost=total_breakdown_cost,
                allocated_costs=allocated_costs,
                profit=r.total_income - allocated_costs,
                allocation_note="Costs are split evenly across a taxi's tagged routes for the period.",
            )
        )

    return RouteProfitabilityResponse(items=items)
