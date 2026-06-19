from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_accountant_or_above, require_owner
from app.database import get_db
from app.models.breakdown import Breakdown
from app.models.depot import Depot
from app.models.driver import Driver
from app.models.employee import Employee
from app.models.fuel import Fuel
from app.models.income import DailyIncome
from app.models.insurance import Insurance
from app.models.mechanic_payment import MechanicPayment
from app.models.organisation_settings import OrganisationSettings
from app.models.remuneration import RemunerationPackage
from app.models.route import Route, RouteAssignment
from app.models.salary_payment import SalaryPayment
from app.models.spare_part import SparePartPurchase
from app.models.taxi import Taxi
from app.models.taxi_loan import LoanPayment, TaxiLoan
from app.models.user import User
from app.schemas.reporting import (
    AssetRegisterItem,
    AssetRegisterResponse,
    BalanceSheetResponse,
    CashFlowResponse,
    DepotCostItem,
    DepotCostResponse,
    DriverPerformanceItem,
    DriverPerformanceResponse,
    ExecutiveSummaryResponse,
    FixedVsVariableItem,
    FixedVsVariableResponse,
    IncomeStatementResponse,
    LoanScheduleItem,
    LoanScheduleResponse,
    MaintenanceDowntimeItem,
    MaintenanceDowntimeResponse,
    PayrollItem,
    PayrollReconciliationResponse,
    PeriodRevenuePoint,
    RevenueByPeriodResponse,
    RouteProfitabilityItem,
    RouteProfitabilityResponse,
    TaxiProfitabilityItem,
    TaxiProfitabilityResponse,
)
from app.api.reports import _calculate_insurance_cost

router = APIRouter(prefix="/reporting", tags=["reporting"])


def _get_settings(db: Session, org_id: str) -> OrganisationSettings:
    settings = db.query(OrganisationSettings).filter(
        OrganisationSettings.organisation_id == org_id
    ).first()
    if not settings:
        settings = OrganisationSettings(organisation_id=org_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def _parse_period(
    start_date: date | None,
    end_date: date | None,
    period: str | None,
) -> tuple[date, date]:
    today = date.today()
    if period == "this_month":
        start_date = today.replace(day=1)
        end_date = today
    elif period == "last_month":
        first = today.replace(day=1)
        end_date = first - timedelta(days=1)
        start_date = end_date.replace(day=1)
    elif period == "this_year":
        start_date = today.replace(month=1, day=1)
        end_date = today
    elif period == "last_year":
        start_date = today.replace(year=today.year - 1, month=1, day=1)
        end_date = today.replace(year=today.year - 1, month=12, day=31)
    else:
        if start_date is None:
            start_date = today.replace(day=1)
        if end_date is None:
            end_date = today
    return start_date, end_date


def _format_csv(rows: list[dict], filename: str) -> Response:
    import csv
    import io

    if not rows:
        return Response(content="", media_type="text/csv", headers={
            "Content-Disposition": f"attachment; filename={filename}"
        })
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/executive-summary", response_model=ExecutiveSummaryResponse)
def executive_summary(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    period: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    start_date, end_date = _parse_period(start_date, end_date, period)
    org_id = user.organisation_id

    revenue = (
        db.query(func.coalesce(func.sum(DailyIncome.total_cash), 0))
        .filter(
            DailyIncome.organisation_id == org_id,
            DailyIncome.date >= start_date,
            DailyIncome.date <= end_date,
        )
        .scalar()
    ) or 0

    fuel = (
        db.query(func.coalesce(func.sum(Fuel.cost_total), 0))
        .filter(
            Fuel.organisation_id == org_id,
            Fuel.date >= start_date,
            Fuel.date <= end_date,
        )
        .scalar()
    ) or 0

    breakdown = (
        db.query(func.coalesce(func.sum(Breakdown.cost_total), 0))
        .filter(
            Breakdown.organisation_id == org_id,
            Breakdown.start_time >= start_date,
            Breakdown.start_time <= end_date,
        )
        .scalar()
    ) or 0

    loan_payments = (
        db.query(func.coalesce(func.sum(LoanPayment.amount_cents), 0))
        .filter(
            LoanPayment.organisation_id == org_id,
            LoanPayment.payment_date >= start_date,
            LoanPayment.payment_date <= end_date,
        )
        .scalar()
    ) or 0

    spare_parts = (
        db.query(func.coalesce(func.sum(SparePartPurchase.cost_total_cents), 0))
        .filter(
            SparePartPurchase.organisation_id == org_id,
            SparePartPurchase.date >= start_date,
            SparePartPurchase.date <= end_date,
        )
        .scalar()
    ) or 0

    mechanic = (
        db.query(func.coalesce(func.sum(MechanicPayment.amount_cents), 0))
        .filter(
            MechanicPayment.organisation_id == org_id,
            MechanicPayment.payment_date >= start_date,
            MechanicPayment.payment_date <= end_date,
        )
        .scalar()
    ) or 0

    salary_paid = (
        db.query(func.coalesce(func.sum(SalaryPayment.amount_cents), 0))
        .filter(
            SalaryPayment.organisation_id == org_id,
            SalaryPayment.payment_date >= start_date,
            SalaryPayment.payment_date <= end_date,
        )
        .scalar()
    ) or 0

    taxis = db.query(Taxi).filter(Taxi.organisation_id == org_id).all()
    insurance = 0
    for t in taxis:
        insurance += _calculate_insurance_cost(db, org_id, t.id, start_date, end_date)

    total_cost = fuel + breakdown + insurance + loan_payments + spare_parts + mechanic + salary_paid
    gross_profit = revenue - total_cost
    margin = round((gross_profit / revenue) * 100, 2) if revenue else 0.0

    active_taxis = sum(1 for t in taxis if t.status == "active")
    total_taxis = len(taxis)
    active_drivers = (
        db.query(func.count(Driver.id))
        .filter(Driver.organisation_id == org_id, Driver.status == "active")
        .scalar()
    ) or 0
    open_breakdowns = (
        db.query(func.count(Breakdown.id))
        .filter(Breakdown.organisation_id == org_id, Breakdown.end_time.is_(None))
        .scalar()
    ) or 0
    loan_exposure = (
        db.query(func.coalesce(func.sum(TaxiLoan.remaining_balance_cents), 0))
        .filter(TaxiLoan.organisation_id == org_id)
        .scalar()
    ) or 0

    # Monthly trend for last 12 months
    trend = []
    for i in range(11, -1, -1):
        m = date.today().replace(day=1) - timedelta(days=1)
        for _ in range(i):
            m = m.replace(day=1) - timedelta(days=1)
        m_start = m.replace(day=1)
        m_end = (m.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        m_revenue = (
            db.query(func.coalesce(func.sum(DailyIncome.total_cash), 0))
            .filter(
                DailyIncome.organisation_id == org_id,
                DailyIncome.date >= m_start,
                DailyIncome.date <= m_end,
            )
            .scalar()
        ) or 0
        m_cost = (
            db.query(func.coalesce(func.sum(Fuel.cost_total), 0))
            .filter(Fuel.organisation_id == org_id, Fuel.date >= m_start, Fuel.date <= m_end)
            .scalar()
        ) or 0
        m_cost += (
            db.query(func.coalesce(func.sum(Breakdown.cost_total), 0))
            .filter(Breakdown.organisation_id == org_id, Breakdown.start_time >= m_start, Breakdown.start_time <= m_end)
            .scalar()
        ) or 0
        trend.append({
            "month": m_start.strftime("%b %Y"),
            "revenue_cents": m_revenue,
            "cost_cents": m_cost,
            "profit_cents": m_revenue - m_cost,
        })

    return ExecutiveSummaryResponse(
        period={"start_date": start_date, "end_date": end_date},
        revenue_cents=revenue,
        total_cost_cents=total_cost,
        gross_profit_cents=gross_profit,
        gross_margin_percent=margin,
        active_taxis=active_taxis,
        total_taxis=total_taxis,
        active_drivers=active_drivers,
        open_breakdowns=open_breakdowns,
        loan_exposure_cents=loan_exposure,
        average_revenue_per_taxi_cents=(revenue // active_taxis) if active_taxis else 0,
        average_cost_per_taxi_cents=(total_cost // active_taxis) if active_taxis else 0,
        trend=trend,
    )


@router.get("/income-statement", response_model=IncomeStatementResponse)
def income_statement(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    period: str | None = Query(None),
    format: Literal["json", "csv"] = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    start_date, end_date = _parse_period(start_date, end_date, period)
    org_id = user.organisation_id

    revenue = (
        db.query(func.coalesce(func.sum(DailyIncome.total_cash), 0))
        .filter(
            DailyIncome.organisation_id == org_id,
            DailyIncome.date >= start_date,
            DailyIncome.date <= end_date,
        )
        .scalar()
    ) or 0

    fuel = (
        db.query(func.coalesce(func.sum(Fuel.cost_total), 0))
        .filter(Fuel.organisation_id == org_id, Fuel.date >= start_date, Fuel.date <= end_date)
        .scalar()
    ) or 0

    breakdown = (
        db.query(func.coalesce(func.sum(Breakdown.cost_total), 0))
        .filter(
            Breakdown.organisation_id == org_id,
            Breakdown.start_time >= start_date,
            Breakdown.start_time <= end_date,
        )
        .scalar()
    ) or 0

    loan_payments = (
        db.query(func.coalesce(func.sum(LoanPayment.amount_cents), 0))
        .filter(
            LoanPayment.organisation_id == org_id,
            LoanPayment.payment_date >= start_date,
            LoanPayment.payment_date <= end_date,
        )
        .scalar()
    ) or 0

    spare_parts = (
        db.query(func.coalesce(func.sum(SparePartPurchase.cost_total_cents), 0))
        .filter(
            SparePartPurchase.organisation_id == org_id,
            SparePartPurchase.date >= start_date,
            SparePartPurchase.date <= end_date,
        )
        .scalar()
    ) or 0

    mechanic = (
        db.query(func.coalesce(func.sum(MechanicPayment.amount_cents), 0))
        .filter(
            MechanicPayment.organisation_id == org_id,
            MechanicPayment.payment_date >= start_date,
            MechanicPayment.payment_date <= end_date,
        )
        .scalar()
    ) or 0

    salary_paid = (
        db.query(func.coalesce(func.sum(SalaryPayment.amount_cents), 0))
        .filter(
            SalaryPayment.organisation_id == org_id,
            SalaryPayment.payment_date >= start_date,
            SalaryPayment.payment_date <= end_date,
        )
        .scalar()
    ) or 0

    taxis = db.query(Taxi).filter(Taxi.organisation_id == org_id).all()
    insurance = 0
    for t in taxis:
        insurance += _calculate_insurance_cost(db, org_id, t.id, start_date, end_date)

    cost_of_operations = fuel + breakdown + insurance + loan_payments + spare_parts + mechanic + salary_paid
    gross_profit = revenue - cost_of_operations
    margin = round((gross_profit / revenue) * 100, 2) if revenue else 0.0

    # Operating expenses placeholder (depots, overheads) — empty until CashBookEntry exists
    operating_expenses = 0
    net_profit = gross_profit - operating_expenses

    if format == "csv":
        rows = [
            {"line": "Revenue", "amount_cents": revenue},
            {"line": "Fuel", "amount_cents": fuel},
            {"line": "Breakdown / Repairs", "amount_cents": breakdown},
            {"line": "Insurance", "amount_cents": insurance},
            {"line": "Hire-Purchase Instalments", "amount_cents": loan_payments},
            {"line": "Spare Parts", "amount_cents": spare_parts},
            {"line": "Mechanic Payments", "amount_cents": mechanic},
            {"line": "Driver Salaries", "amount_cents": salary_paid},
            {"line": "Total Cost of Operations", "amount_cents": cost_of_operations},
            {"line": "Gross Profit", "amount_cents": gross_profit},
            {"line": "Operating Expenses", "amount_cents": operating_expenses},
            {"line": "Net Profit Before Tax", "amount_cents": net_profit},
        ]
        return _format_csv(rows, f"income_statement_{start_date}_{end_date}.csv")

    return IncomeStatementResponse(
        period={"start_date": start_date, "end_date": end_date},
        revenue_cents=revenue,
        fuel_cents=fuel,
        breakdown_cents=breakdown,
        insurance_cents=insurance,
        loan_payment_cents=loan_payments,
        spare_part_cents=spare_parts,
        mechanic_payment_cents=mechanic,
        salary_cents=salary_paid,
        cost_of_operations_cents=cost_of_operations,
        gross_profit_cents=gross_profit,
        gross_margin_percent=margin,
        operating_expenses_cents=operating_expenses,
        net_profit_cents=net_profit,
    )


@router.get("/cash-flow", response_model=CashFlowResponse)
def cash_flow(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    period: str | None = Query(None),
    format: Literal["json", "csv"] = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    start_date, end_date = _parse_period(start_date, end_date, period)
    org_id = user.organisation_id

    cash_in = (
        db.query(func.coalesce(func.sum(DailyIncome.total_cash), 0))
        .filter(
            DailyIncome.organisation_id == org_id,
            DailyIncome.date >= start_date,
            DailyIncome.date <= end_date,
        )
        .scalar()
    ) or 0

    fuel = (
        db.query(func.coalesce(func.sum(Fuel.cost_total), 0))
        .filter(Fuel.organisation_id == org_id, Fuel.date >= start_date, Fuel.date <= end_date)
        .scalar()
    ) or 0

    breakdown = (
        db.query(func.coalesce(func.sum(Breakdown.cost_total), 0))
        .filter(
            Breakdown.organisation_id == org_id,
            Breakdown.start_time >= start_date,
            Breakdown.start_time <= end_date,
        )
        .scalar()
    ) or 0

    loan_payments = (
        db.query(func.coalesce(func.sum(LoanPayment.amount_cents), 0))
        .filter(
            LoanPayment.organisation_id == org_id,
            LoanPayment.payment_date >= start_date,
            LoanPayment.payment_date <= end_date,
        )
        .scalar()
    ) or 0

    spare_parts = (
        db.query(func.coalesce(func.sum(SparePartPurchase.cost_total_cents), 0))
        .filter(
            SparePartPurchase.organisation_id == org_id,
            SparePartPurchase.date >= start_date,
            SparePartPurchase.date <= end_date,
        )
        .scalar()
    ) or 0

    mechanic = (
        db.query(func.coalesce(func.sum(MechanicPayment.amount_cents), 0))
        .filter(
            MechanicPayment.organisation_id == org_id,
            MechanicPayment.payment_date >= start_date,
            MechanicPayment.payment_date <= end_date,
        )
        .scalar()
    ) or 0

    salaries = (
        db.query(func.coalesce(func.sum(SalaryPayment.amount_cents), 0))
        .filter(
            SalaryPayment.organisation_id == org_id,
            SalaryPayment.payment_date >= start_date,
            SalaryPayment.payment_date <= end_date,
        )
        .scalar()
    ) or 0

    taxis = db.query(Taxi).filter(Taxi.organisation_id == org_id).all()
    insurance = 0
    for t in taxis:
        insurance += _calculate_insurance_cost(db, org_id, t.id, start_date, end_date)

    total_cash_out = fuel + breakdown + insurance + loan_payments + spare_parts + mechanic + salaries
    net_movement = cash_in - total_cash_out

    if format == "csv":
        rows = [
            {"line": "Cash Received — Daily Income", "amount_cents": cash_in},
            {"line": "Fuel", "amount_cents": -fuel},
            {"line": "Breakdown / Repairs", "amount_cents": -breakdown},
            {"line": "Insurance", "amount_cents": -insurance},
            {"line": "Hire-Purchase Payments", "amount_cents": -loan_payments},
            {"line": "Spare Parts", "amount_cents": -spare_parts},
            {"line": "Mechanic Payments", "amount_cents": -mechanic},
            {"line": "Salaries Paid", "amount_cents": -salaries},
            {"line": "Total Cash Out", "amount_cents": -total_cash_out},
            {"line": "Net Cash Movement", "amount_cents": net_movement},
        ]
        return _format_csv(rows, f"cash_flow_{start_date}_{end_date}.csv")

    return CashFlowResponse(
        period={"start_date": start_date, "end_date": end_date},
        cash_in_cents=cash_in,
        fuel_cents=fuel,
        breakdown_cents=breakdown,
        insurance_cents=insurance,
        loan_payment_cents=loan_payments,
        spare_part_cents=spare_parts,
        mechanic_payment_cents=mechanic,
        salary_cents=salaries,
        total_cash_out_cents=total_cash_out,
        net_cash_movement_cents=net_movement,
    )


@router.get("/balance-sheet", response_model=BalanceSheetResponse)
def balance_sheet(
    as_at: date | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    if as_at is None:
        as_at = date.today()
    org_id = user.organisation_id

    taxi_assets = (
        db.query(func.coalesce(func.sum(TaxiLoan.total_amount_cents), 0))
        .filter(TaxiLoan.organisation_id == org_id)
        .scalar()
    ) or 0

    spare_parts_inventory = (
        db.query(func.coalesce(func.sum(SparePartPurchase.cost_total_cents), 0))
        .filter(
            SparePartPurchase.organisation_id == org_id,
            SparePartPurchase.date <= as_at,
        )
        .scalar()
    ) or 0

    cash_in = (
        db.query(func.coalesce(func.sum(DailyIncome.total_cash), 0))
        .filter(DailyIncome.organisation_id == org_id, DailyIncome.date <= as_at)
        .scalar()
    ) or 0
    cash_out = (
        db.query(func.coalesce(func.sum(Fuel.cost_total), 0))
        .filter(Fuel.organisation_id == org_id, Fuel.date <= as_at)
        .scalar()
    ) or 0
    cash_out += (
        db.query(func.coalesce(func.sum(Breakdown.cost_total), 0))
        .filter(Breakdown.organisation_id == org_id, Breakdown.start_time <= as_at)
        .scalar()
    ) or 0
    cash_out += (
        db.query(func.coalesce(func.sum(LoanPayment.amount_cents), 0))
        .filter(LoanPayment.organisation_id == org_id, LoanPayment.payment_date <= as_at)
        .scalar()
    ) or 0
    cash_out += (
        db.query(func.coalesce(func.sum(SparePartPurchase.cost_total_cents), 0))
        .filter(SparePartPurchase.organisation_id == org_id, SparePartPurchase.date <= as_at)
        .scalar()
    ) or 0
    cash_out += (
        db.query(func.coalesce(func.sum(MechanicPayment.amount_cents), 0))
        .filter(MechanicPayment.organisation_id == org_id, MechanicPayment.payment_date <= as_at)
        .scalar()
    ) or 0
    cash_out += (
        db.query(func.coalesce(func.sum(SalaryPayment.amount_cents), 0))
        .filter(SalaryPayment.organisation_id == org_id, SalaryPayment.payment_date <= as_at)
        .scalar()
    ) or 0
    cash_balance = cash_in - cash_out

    loan_outstanding = (
        db.query(func.coalesce(func.sum(TaxiLoan.remaining_balance_cents), 0))
        .filter(TaxiLoan.organisation_id == org_id)
        .scalar()
    ) or 0

    total_assets = taxi_assets + spare_parts_inventory + cash_balance
    total_liabilities = loan_outstanding
    equity = total_assets - total_liabilities

    return BalanceSheetResponse(
        as_at=as_at,
        taxi_assets_cents=taxi_assets,
        spare_parts_inventory_cents=spare_parts_inventory,
        cash_balance_cents=cash_balance,
        total_assets_cents=total_assets,
        loan_outstanding_cents=loan_outstanding,
        total_liabilities_cents=total_liabilities,
        equity_cents=equity,
    )


@router.get("/taxi-profitability", response_model=TaxiProfitabilityResponse)
def taxi_profitability(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    period: str | None = Query(None),
    taxi_id: str | None = Query(None),
    format: Literal["json", "csv"] = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    start_date, end_date = _parse_period(start_date, end_date, period)
    org_id = user.organisation_id

    taxi_q = db.query(Taxi).filter(Taxi.organisation_id == org_id)
    if taxi_id:
        taxi_q = taxi_q.filter(Taxi.id == taxi_id)
    taxis = taxi_q.all()

    routes = {r.id: r.name for r in db.query(Route).filter(Route.organisation_id == org_id).all()}

    income_q = db.query(
        DailyIncome.taxi_id,
        func.coalesce(func.sum(DailyIncome.total_cash), 0).label("total_income"),
        func.count(func.distinct(DailyIncome.date)).label("days_active"),
    ).filter(
        DailyIncome.organisation_id == org_id,
        DailyIncome.date >= start_date,
        DailyIncome.date <= end_date,
    ).group_by(DailyIncome.taxi_id)
    income_rows = {r.taxi_id: r for r in income_q.all()}

    fuel_q = db.query(
        Fuel.taxi_id,
        func.coalesce(func.sum(Fuel.cost_total), 0).label("total_fuel"),
    ).filter(
        Fuel.organisation_id == org_id,
        Fuel.date >= start_date,
        Fuel.date <= end_date,
    ).group_by(Fuel.taxi_id)
    fuel_rows = {r.taxi_id: r.total_fuel for r in fuel_q.all()}

    bd_q = db.query(
        Breakdown.taxi_id,
        func.coalesce(func.sum(Breakdown.cost_total), 0).label("total_breakdown"),
    ).filter(
        Breakdown.organisation_id == org_id,
        Breakdown.start_time >= start_date,
        Breakdown.start_time <= end_date,
    ).group_by(Breakdown.taxi_id)
    bd_rows = {r.taxi_id: r.total_breakdown for r in bd_q.all()}

    loan_q = db.query(
        LoanPayment.loan_id,
        func.coalesce(func.sum(LoanPayment.amount_cents), 0).label("total_loan_payments"),
    ).filter(
        LoanPayment.organisation_id == org_id,
        LoanPayment.payment_date >= start_date,
        LoanPayment.payment_date <= end_date,
    ).group_by(LoanPayment.loan_id)
    loan_rows = {r.loan_id: r.total_loan_payments for r in loan_q.all()}

    loan_to_taxi = {
        l.id: l.taxi_id
        for l in db.query(TaxiLoan.id, TaxiLoan.taxi_id).filter(TaxiLoan.organisation_id == org_id).all()
    }

    sp_q = db.query(
        SparePartPurchase.taxi_id,
        func.coalesce(func.sum(SparePartPurchase.cost_total_cents), 0).label("total"),
    ).filter(
        SparePartPurchase.organisation_id == org_id,
        SparePartPurchase.taxi_id.isnot(None),
        SparePartPurchase.date >= start_date,
        SparePartPurchase.date <= end_date,
    ).group_by(SparePartPurchase.taxi_id)
    sp_rows = {r.taxi_id: r.total for r in sp_q.all()}

    mp_q = db.query(
        MechanicPayment.taxi_id,
        func.coalesce(func.sum(MechanicPayment.amount_cents), 0).label("total"),
    ).filter(
        MechanicPayment.organisation_id == org_id,
        MechanicPayment.taxi_id.isnot(None),
        MechanicPayment.payment_date >= start_date,
        MechanicPayment.payment_date <= end_date,
    ).group_by(MechanicPayment.taxi_id)
    mp_rows = {r.taxi_id: r.total for r in mp_q.all()}

    # Driver salary owed for assigned driver(s)
    driver_map = {d.assigned_taxi_id: d for d in db.query(Driver).filter(Driver.organisation_id == org_id).all()}
    employee_map = {}
    for e in db.query(Employee).filter(Employee.organisation_id == org_id).all():
        employee_map[e.driver_id] = e
    package_map = {p.id: p for p in db.query(RemunerationPackage).filter(RemunerationPackage.organisation_id == org_id).all()}

    def _salary_owed(driver_id: str) -> int:
        emp = employee_map.get(driver_id)
        if not emp or not emp.remuneration_package_id:
            return 0
        pkg = package_map.get(emp.remuneration_package_id)
        if not pkg:
            return 0
        hire = max(emp.hire_date, start_date)
        term = emp.termination_date or end_date
        term = min(term, end_date)
        days_employed = max(0, (term - hire).days + 1)
        days_in_period = max(1, (end_date - start_date).days + 1)
        if pkg.payment_frequency == "weekly":
            return int(pkg.base_salary_cents * days_employed / 7)
        return int(pkg.base_salary_cents * days_employed / days_in_period)

    items = []
    for t in taxis:
        inc = income_rows.get(t.id)
        income = inc.total_income if inc else 0
        days_active = inc.days_active if inc else 0
        fuel = fuel_rows.get(t.id, 0)
        bd = bd_rows.get(t.id, 0)
        loan_cost = sum(loan_rows.get(lid, 0) for lid, tid in loan_to_taxi.items() if tid == t.id)
        insurance = _calculate_insurance_cost(db, org_id, t.id, start_date, end_date)
        sp = sp_rows.get(t.id, 0)
        mp = mp_rows.get(t.id, 0)

        driver = driver_map.get(t.id)
        salary_owed = _salary_owed(driver.id) if driver else 0

        total_cost = fuel + bd + loan_cost + insurance + sp + mp + salary_owed
        net_profit = income - total_cost
        margin = round((net_profit / income) * 100, 2) if income else 0.0
        cost_per_day = (total_cost // days_active) if days_active else 0

        items.append(TaxiProfitabilityItem(
            taxi_id=t.id,
            registration_number=t.registration_number,
            route_name=routes.get(t.assigned_route_id),
            days_active=days_active,
            total_income_cents=income,
            fuel_cents=fuel,
            breakdown_cents=bd,
            insurance_cents=insurance,
            loan_payment_cents=loan_cost,
            spare_part_cents=sp,
            mechanic_payment_cents=mp,
            driver_salary_owed_cents=salary_owed,
            total_cost_cents=total_cost,
            net_profit_cents=net_profit,
            profit_margin_percent=margin,
            cost_per_active_day_cents=cost_per_day,
        ))

    summary = {
        "total_income_cents": sum(i.total_income_cents for i in items),
        "total_cost_cents": sum(i.total_cost_cents for i in items),
        "total_net_profit_cents": sum(i.net_profit_cents for i in items),
        "taxi_count": len(items),
    }

    if format == "csv":
        rows = [i.model_dump() for i in items]
        return _format_csv(rows, f"taxi_profitability_{start_date}_{end_date}.csv")

    return TaxiProfitabilityResponse(period={"start_date": start_date, "end_date": end_date}, items=items, summary=summary)


@router.get("/driver-performance", response_model=DriverPerformanceResponse)
def driver_performance_report(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    period: str | None = Query(None),
    driver_id: str | None = Query(None),
    format: Literal["json", "csv"] = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    start_date, end_date = _parse_period(start_date, end_date, period)
    org_id = user.organisation_id
    days_in_period = max(1, (end_date - start_date).days + 1)

    driver_q = db.query(Driver).filter(Driver.organisation_id == org_id)
    if driver_id:
        driver_q = driver_q.filter(Driver.id == driver_id)
    drivers = driver_q.all()

    taxis = {t.id: t.registration_number for t in db.query(Taxi).filter(Taxi.organisation_id == org_id).all()}

    income_q = db.query(
        DailyIncome.driver_id,
        func.coalesce(func.sum(DailyIncome.total_cash), 0).label("total_income"),
        func.count(func.distinct(DailyIncome.date)).label("income_days"),
    ).filter(
        DailyIncome.organisation_id == org_id,
        DailyIncome.date >= start_date,
        DailyIncome.date <= end_date,
    ).group_by(DailyIncome.driver_id)
    income_rows = {r.driver_id: r for r in income_q.all()}

    employees = {e.driver_id: e for e in db.query(Employee).filter(Employee.organisation_id == org_id).all()}
    packages = {p.id: p for p in db.query(RemunerationPackage).filter(RemunerationPackage.organisation_id == org_id).all()}

    salary_paid_q = db.query(
        SalaryPayment.employee_id,
        func.coalesce(func.sum(SalaryPayment.amount_cents), 0).label("total"),
    ).filter(
        SalaryPayment.organisation_id == org_id,
        SalaryPayment.payment_date >= start_date,
        SalaryPayment.payment_date <= end_date,
    ).group_by(SalaryPayment.employee_id)
    salary_paid_rows = {r.employee_id: r.total for r in salary_paid_q.all()}

    items = []
    for d in drivers:
        inc = income_rows.get(d.id)
        income = inc.total_income if inc else 0
        income_days = inc.income_days if inc else 0
        idle_days = max(0, days_in_period - income_days)

        emp = employees.get(d.id)
        pkg = packages.get(emp.remuneration_package_id) if emp and emp.remuneration_package_id else None
        salary_owed = 0
        if emp and pkg:
            hire = max(emp.hire_date, start_date)
            term = emp.termination_date or end_date
            term = min(term, end_date)
            days_employed = max(0, (term - hire).days + 1)
            if pkg.payment_frequency == "weekly":
                salary_owed = int(pkg.base_salary_cents * days_employed / 7)
            else:
                salary_owed = int(pkg.base_salary_cents * days_employed / days_in_period)

        salary_paid = salary_paid_rows.get(emp.id, 0) if emp else 0
        income_per_day = (income // income_days) if income_days else 0

        items.append(DriverPerformanceItem(
            driver_id=d.id,
            driver_name=d.name,
            taxi_registration=taxis.get(d.assigned_taxi_id),
            income_days=income_days,
            idle_days=idle_days,
            total_income_cents=income,
            package_name=pkg.name if pkg else None,
            payment_frequency=pkg.payment_frequency if pkg else None,
            salary_owed_cents=salary_owed,
            salary_paid_cents=salary_paid,
            salary_balance_cents=salary_owed - salary_paid,
            income_per_active_day_cents=income_per_day,
        ))

    summary = {
        "total_income_cents": sum(i.total_income_cents for i in items),
        "total_salary_owed_cents": sum(i.salary_owed_cents for i in items),
        "total_salary_paid_cents": sum(i.salary_paid_cents for i in items),
        "total_idle_days": sum(i.idle_days for i in items),
    }

    if format == "csv":
        rows = [i.model_dump() for i in items]
        return _format_csv(rows, f"driver_performance_{start_date}_{end_date}.csv")

    return DriverPerformanceResponse(period={"start_date": start_date, "end_date": end_date}, items=items, summary=summary)


@router.get("/route-profitability", response_model=RouteProfitabilityResponse)
def route_profitability_report(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    period: str | None = Query(None),
    route_id: str | None = Query(None),
    format: Literal["json", "csv"] = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    start_date, end_date = _parse_period(start_date, end_date, period)
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
    ).filter(
        Route.organisation_id == org_id,
        DailyIncome.date >= start_date,
        DailyIncome.date <= end_date,
    )
    if route_id:
        income_q = income_q.filter(Route.id == route_id)
    income_q = income_q.group_by(Route.id, Route.name, Route.distance_km)
    route_data = income_q.all()

    # Pre-compute cost allocations per route
    # For each route, find taxis that tagged this route and allocate a share of their costs
    # proportional to number of routes that taxi used in the period.
    items = []
    for r in route_data:
        route_income_ids = db.query(RouteAssignment.daily_income_id).filter(
            RouteAssignment.route_id == r.route_id,
        ).subquery()
        taxi_ids_in_route = db.query(DailyIncome.taxi_id).filter(
            DailyIncome.id.in_(route_income_ids),
        ).distinct().all()
        taxi_ids = [t[0] for t in taxi_ids_in_route]

        allocated_fuel = 0
        allocated_breakdown = 0
        allocated_salary = 0
        allocated_insurance = 0
        allocated_loan = 0

        for tid in taxi_ids:
            # Count how many distinct routes this taxi tagged in period
            taxi_route_count = db.query(func.count(func.distinct(RouteAssignment.route_id))).filter(
                RouteAssignment.daily_income_id.in_(
                    db.query(DailyIncome.id).filter(
                        DailyIncome.taxi_id == tid,
                        DailyIncome.date >= start_date,
                        DailyIncome.date <= end_date,
                    )
                ),
            ).scalar() or 1
            share = 1 / taxi_route_count

            allocated_fuel += (db.query(func.coalesce(func.sum(Fuel.cost_total), 0)).filter(
                Fuel.taxi_id == tid, Fuel.date >= start_date, Fuel.date <= end_date
            ).scalar() or 0) * share

            allocated_breakdown += (db.query(func.coalesce(func.sum(Breakdown.cost_total), 0)).filter(
                Breakdown.taxi_id == tid, Breakdown.start_time >= start_date, Breakdown.start_time <= end_date
            ).scalar() or 0) * share

            allocated_insurance += _calculate_insurance_cost(db, org_id, tid, start_date, end_date) * share

            loan_ids = [l.id for l in db.query(TaxiLoan.id).filter(
                TaxiLoan.taxi_id == tid, TaxiLoan.organisation_id == org_id
            ).all()]
            loan_payments = (db.query(func.coalesce(func.sum(LoanPayment.amount_cents), 0)).filter(
                LoanPayment.loan_id.in_(loan_ids),
                LoanPayment.payment_date >= start_date,
                LoanPayment.payment_date <= end_date,
            ).scalar() or 0) * share
            allocated_loan += loan_payments

            # Driver salary allocation
            driver = db.query(Driver).filter(Driver.assigned_taxi_id == tid, Driver.organisation_id == org_id).first()
            if driver:
                emp = db.query(Employee).filter(
                    Employee.driver_id == driver.id, Employee.organisation_id == org_id
                ).first()
                pkg = db.query(RemunerationPackage).filter(
                    RemunerationPackage.id == emp.remuneration_package_id
                ).first() if emp and emp.remuneration_package_id else None
                if emp and pkg:
                    hire = max(emp.hire_date, start_date)
                    term = emp.termination_date or end_date
                    term = min(term, end_date)
                    days_employed = max(0, (term - hire).days + 1)
                    days_in_period = max(1, (end_date - start_date).days + 1)
                    if pkg.payment_frequency == "weekly":
                        owed = int(pkg.base_salary_cents * days_employed / 7)
                    else:
                        owed = int(pkg.base_salary_cents * days_employed / days_in_period)
                    allocated_salary += owed * share

        total_cost = int(allocated_fuel + allocated_breakdown + allocated_salary + allocated_insurance + allocated_loan)
        profit = r.total_income - total_cost
        profit_per_km = int(profit / r.distance_km) if r.distance_km else None
        profit_per_trip = int(profit / r.income_count) if r.income_count else None

        items.append(RouteProfitabilityItem(
            route_id=r.route_id,
            route_name=r.route_name,
            distance_km=r.distance_km,
            income_count=r.income_count,
            total_income_cents=r.total_income,
            allocated_fuel_cents=int(allocated_fuel),
            allocated_breakdown_cents=int(allocated_breakdown),
            allocated_salary_cents=int(allocated_salary),
            allocated_insurance_cents=int(allocated_insurance),
            allocated_loan_cents=int(allocated_loan),
            total_allocated_cost_cents=total_cost,
            profit_cents=profit,
            profit_per_km_cents=profit_per_km,
            profit_per_trip_cents=profit_per_trip,
        ))

    if format == "csv":
        rows = [i.model_dump() for i in items]
        return _format_csv(rows, f"route_profitability_{start_date}_{end_date}.csv")

    return RouteProfitabilityResponse(period={"start_date": start_date, "end_date": end_date}, items=items)


@router.get("/depot-costs", response_model=DepotCostResponse)
def depot_costs(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    period: str | None = Query(None),
    depot_id: str | None = Query(None),
    format: Literal["json", "csv"] = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    start_date, end_date = _parse_period(start_date, end_date, period)
    org_id = user.organisation_id

    depot_q = db.query(Depot).filter(Depot.organisation_id == org_id)
    if depot_id:
        depot_q = depot_q.filter(Depot.id == depot_id)
    depots = depot_q.all()

    employees = {e.depot_id: e for e in db.query(Employee).filter(Employee.organisation_id == org_id).all()}
    packages = {p.id: p for p in db.query(RemunerationPackage).filter(RemunerationPackage.organisation_id == org_id).all()}

    def _employee_salary_owed(emp: Employee) -> int:
        if not emp or not emp.remuneration_package_id:
            return 0
        pkg = packages.get(emp.remuneration_package_id)
        if not pkg:
            return 0
        hire = max(emp.hire_date, start_date)
        term = emp.termination_date or end_date
        term = min(term, end_date)
        days_employed = max(0, (term - hire).days + 1)
        days_in_period = max(1, (end_date - start_date).days + 1)
        if pkg.payment_frequency == "weekly":
            return int(pkg.base_salary_cents * days_employed / 7)
        return int(pkg.base_salary_cents * days_employed / days_in_period)

    items = []
    for d in depots:
        employees_assigned = db.query(func.count(Employee.id)).filter(
            Employee.depot_id == d.id, Employee.organisation_id == org_id
        ).scalar() or 0

        spare_parts = (db.query(func.coalesce(func.sum(SparePartPurchase.cost_total_cents), 0)).filter(
            SparePartPurchase.depot_id == d.id,
            SparePartPurchase.organisation_id == org_id,
            SparePartPurchase.date >= start_date,
            SparePartPurchase.date <= end_date,
        ).scalar() or 0)

        mechanic = (db.query(func.coalesce(func.sum(MechanicPayment.amount_cents), 0)).filter(
            MechanicPayment.depot_id == d.id,
            MechanicPayment.organisation_id == org_id,
            MechanicPayment.payment_date >= start_date,
            MechanicPayment.payment_date <= end_date,
        ).scalar() or 0)

        internal_labour = sum(
            _employee_salary_owed(e)
            for e in db.query(Employee).filter(Employee.depot_id == d.id, Employee.organisation_id == org_id).all()
        )

        taxi_ids = db.query(SparePartPurchase.taxi_id).filter(
            SparePartPurchase.depot_id == d.id,
            SparePartPurchase.taxi_id.isnot(None),
            SparePartPurchase.date >= start_date,
            SparePartPurchase.date <= end_date,
        ).union(
            db.query(MechanicPayment.taxi_id).filter(
                MechanicPayment.depot_id == d.id,
                MechanicPayment.taxi_id.isnot(None),
                MechanicPayment.payment_date >= start_date,
                MechanicPayment.payment_date <= end_date,
            )
        ).distinct().all()
        taxis_serviced = len([t[0] for t in taxi_ids if t[0]])

        total_cost = spare_parts + mechanic + internal_labour
        cost_per_taxi = int(total_cost // taxis_serviced) if taxis_serviced else None
        cost_per_employee = int(total_cost // employees_assigned) if employees_assigned else None

        items.append(DepotCostItem(
            depot_id=d.id,
            depot_name=d.name,
            depot_type=d.depot_type,
            employees_assigned=employees_assigned,
            spare_parts_cents=spare_parts,
            mechanic_payments_cents=mechanic,
            internal_labour_cents=internal_labour,
            taxis_serviced=taxis_serviced,
            total_cost_cents=total_cost,
            cost_per_taxi_cents=cost_per_taxi,
            cost_per_employee_cents=cost_per_employee,
        ))

    if format == "csv":
        rows = [i.model_dump() for i in items]
        return _format_csv(rows, f"depot_costs_{start_date}_{end_date}.csv")

    return DepotCostResponse(period={"start_date": start_date, "end_date": end_date}, items=items)


@router.get("/maintenance-downtime", response_model=MaintenanceDowntimeResponse)
def maintenance_downtime(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    period: str | None = Query(None),
    taxi_id: str | None = Query(None),
    format: Literal["json", "csv"] = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    start_date, end_date = _parse_period(start_date, end_date, period)
    # Adjust end_date to include the full day (compare datetime <= end_of_day)
    end_date_exclusive = end_date + timedelta(days=1)
    org_id = user.organisation_id

    q = db.query(
        Breakdown,
        Taxi.registration_number.label("registration_number"),
    ).join(Taxi, Breakdown.taxi_id == Taxi.id).filter(
        Breakdown.organisation_id == org_id,
        Breakdown.start_time >= start_date,
        Breakdown.start_time < end_date_exclusive,
    )
    if taxi_id:
        q = q.filter(Breakdown.taxi_id == taxi_id)
    q = q.order_by(Breakdown.start_time.desc())

    total_cost = 0
    total_lost_revenue = 0
    items = []
    for row in q.all():
        b, reg = row
        cost = b.cost_total or 0
        total_cost += cost

        duration = timedelta()
        if b.end_time:
            duration = b.end_time - b.start_time
        duration_hours = duration.total_seconds() / 3600
        downtime_days = max(1, int(duration_hours // 24) + (1 if duration_hours % 24 else 0))

        # Lost revenue estimate: average daily income for this taxi in the 30 days before breakdown
        avg_daily = (
            db.query(func.coalesce(func.sum(DailyIncome.total_cash), 0))
            .filter(
                DailyIncome.taxi_id == b.taxi_id,
                DailyIncome.date >= b.start_time.date() - timedelta(days=30),
                DailyIncome.date < b.start_time.date(),
            )
            .scalar()
        ) or 0
        active_days = (
            db.query(func.count(func.distinct(DailyIncome.date)))
            .filter(
                DailyIncome.taxi_id == b.taxi_id,
                DailyIncome.date >= b.start_time.date() - timedelta(days=30),
                DailyIncome.date < b.start_time.date(),
            )
            .scalar()
        ) or 1
        avg_daily = avg_daily // active_days
        lost_revenue = avg_daily * downtime_days
        total_lost_revenue += lost_revenue

        items.append(MaintenanceDowntimeItem(
            breakdown_id=b.id,
            taxi_id=b.taxi_id,
            registration_number=reg,
            reason=b.reason,
            start_time=b.start_time,
            end_time=b.end_time,
            duration_hours=duration_hours,
            cost_total_cents=cost,
            downtime_days=downtime_days,
            lost_revenue_estimate_cents=lost_revenue,
        ))

    if format == "csv":
        rows = [i.model_dump() for i in items]
        return _format_csv(rows, f"maintenance_downtime_{start_date}_{end_date}.csv")

    return MaintenanceDowntimeResponse(
        period={"start_date": start_date, "end_date": end_date},
        items=items,
        total_cost_cents=total_cost,
        total_lost_revenue_cents=total_lost_revenue,
    )


# ── Phase C — Financial Deep-Dive ──────────────────────────────────────────


@router.get("/fixed-vs-variable", response_model=FixedVsVariableResponse)
def fixed_vs_variable(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    period: str | None = Query(None),
    format: Literal["json", "csv"] = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    start_date, end_date = _parse_period(start_date, end_date, period)
    org_id = user.organisation_id

    fuel = (
        db.query(func.coalesce(func.sum(Fuel.cost_total), 0))
        .filter(Fuel.organisation_id == org_id, Fuel.date >= start_date, Fuel.date <= end_date)
        .scalar()
    ) or 0
    breakdown = (
        db.query(func.coalesce(func.sum(Breakdown.cost_total), 0))
        .filter(Breakdown.organisation_id == org_id, Breakdown.start_time >= start_date, Breakdown.start_time <= end_date)
        .scalar()
    ) or 0
    loan_payments = (
        db.query(func.coalesce(func.sum(LoanPayment.amount_cents), 0))
        .filter(LoanPayment.organisation_id == org_id, LoanPayment.payment_date >= start_date, LoanPayment.payment_date <= end_date)
        .scalar()
    ) or 0
    spare_parts = (
        db.query(func.coalesce(func.sum(SparePartPurchase.cost_total_cents), 0))
        .filter(SparePartPurchase.organisation_id == org_id, SparePartPurchase.date >= start_date, SparePartPurchase.date <= end_date)
        .scalar()
    ) or 0
    mechanic = (
        db.query(func.coalesce(func.sum(MechanicPayment.amount_cents), 0))
        .filter(MechanicPayment.organisation_id == org_id, MechanicPayment.payment_date >= start_date, MechanicPayment.payment_date <= end_date)
        .scalar()
    ) or 0

    taxis = db.query(Taxi).filter(Taxi.organisation_id == org_id).all()
    insurance = 0
    for t in taxis:
        insurance += _calculate_insurance_cost(db, org_id, t.id, start_date, end_date)

    salary_owed = 0
    employees = db.query(Employee).filter(Employee.organisation_id == org_id).all()
    packages = {p.id: p for p in db.query(RemunerationPackage).filter(RemunerationPackage.organisation_id == org_id).all()}
    days_in_period = max(1, (end_date - start_date).days + 1)
    for emp in employees:
        if not emp.remuneration_package_id:
            continue
        pkg = packages.get(emp.remuneration_package_id)
        if not pkg:
            continue
        hire = max(emp.hire_date, start_date) if emp.hire_date else start_date
        term = emp.termination_date or end_date
        term = min(term, end_date)
        days_emp = max(0, (term - hire).days + 1)
        if pkg.payment_frequency == "weekly":
            salary_owed += int(pkg.base_salary_cents * days_emp / 7)
        else:
            salary_owed += int(pkg.base_salary_cents * days_emp / days_in_period)

    total = fuel + breakdown + loan_payments + spare_parts + mechanic + insurance + salary_owed

    items = [
        FixedVsVariableItem(category="Insurance", cost_type="Fixed", amount_cents=insurance, percentage=round((insurance / total) * 100, 2) if total else 0.0),
        FixedVsVariableItem(category="Hire-Purchase Instalments", cost_type="Fixed", amount_cents=loan_payments, percentage=round((loan_payments / total) * 100, 2) if total else 0.0),
        FixedVsVariableItem(category="Salaries (Fixed Portion)", cost_type="Fixed", amount_cents=salary_owed, percentage=round((salary_owed / total) * 100, 2) if total else 0.0),
        FixedVsVariableItem(category="Fuel", cost_type="Variable", amount_cents=fuel, percentage=round((fuel / total) * 100, 2) if total else 0.0),
        FixedVsVariableItem(category="Breakdowns", cost_type="Variable", amount_cents=breakdown, percentage=round((breakdown / total) * 100, 2) if total else 0.0),
        FixedVsVariableItem(category="Spare Parts", cost_type="Variable", amount_cents=spare_parts, percentage=round((spare_parts / total) * 100, 2) if total else 0.0),
        FixedVsVariableItem(category="Mechanic Payments", cost_type="Variable", amount_cents=mechanic, percentage=round((mechanic / total) * 100, 2) if total else 0.0),
    ]

    total_fixed = insurance + loan_payments + salary_owed
    total_variable = fuel + breakdown + spare_parts + mechanic

    if format == "csv":
        rows = [i.model_dump() for i in items]
        return _format_csv(rows, f"fixed_vs_variable_{start_date}_{end_date}.csv")

    return FixedVsVariableResponse(
        period={"start_date": start_date, "end_date": end_date},
        items=items,
        total_fixed_cents=total_fixed,
        total_variable_cents=total_variable,
        fixed_percentage=round((total_fixed / total) * 100, 2) if total else 0.0,
        variable_percentage=round((total_variable / total) * 100, 2) if total else 0.0,
    )


@router.get("/revenue-by-period", response_model=RevenueByPeriodResponse)
def revenue_by_period(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    period: str | None = Query(None),
    group_by: str = Query("month"),
    format: Literal["json", "csv"] = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    start_date, end_date = _parse_period(start_date, end_date, period)
    org_id = user.organisation_id

    # Calculate period length for previous period comparison
    period_days = (end_date - start_date).days + 1
    prev_start = start_date - timedelta(days=period_days)
    prev_end = start_date - timedelta(days=1)

    # Helper to build series
    def _revenue_series(sd: date, ed: date) -> int:
        return (
            db.query(func.coalesce(func.sum(DailyIncome.total_cash), 0))
            .filter(DailyIncome.organisation_id == org_id, DailyIncome.date >= sd, DailyIncome.date <= ed)
            .scalar()
        ) or 0

    total_current = _revenue_series(start_date, end_date)
    total_previous = _revenue_series(prev_start, prev_end)
    change = total_current - total_previous
    change_pct = round((change / total_previous) * 100, 2) if total_previous else None

    # Build sub-periods within the range
    import calendar
    series = []
    cursor = start_date
    while cursor <= end_date:
        if group_by == "day":
            seg_start = cursor
            seg_end = cursor
            label = cursor.strftime("%d %b")
            next_step = seg_end + timedelta(days=1)
        elif group_by == "week":
            seg_start = cursor
            seg_end = min(cursor + timedelta(days=6), end_date)
            label = f"{seg_start.strftime('%d %b')} - {seg_end.strftime('%d %b')}"
            next_step = seg_end + timedelta(days=1)
        elif group_by == "quarter":
            q = (cursor.month - 1) // 3 + 1
            seg_start = cursor
            seg_end = min((seg_start.replace(day=28) + timedelta(days=116)).replace(day=1) - timedelta(days=1), end_date)
            label = f"Q{q} {cursor.year}"
            next_step = seg_end + timedelta(days=1)
        else:  # month (default)
            seg_start = cursor
            last_day = calendar.monthrange(cursor.year, cursor.month)[1]
            seg_end = min(cursor.replace(day=last_day), end_date)
            label = cursor.strftime("%b %Y")
            next_step = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)

        # Previous period same sub-period
        prev_seg_start = seg_start - timedelta(days=period_days)
        prev_seg_end = seg_end - timedelta(days=period_days)
        prev_rev = _revenue_series(prev_seg_start, prev_seg_end)

        rev = _revenue_series(seg_start, seg_end)
        series.append(PeriodRevenuePoint(label=label, revenue_cents=rev, previous_revenue_cents=prev_rev))
        cursor = next_step

    if format == "csv":
        rows = [
            {"label": s.label, "revenue_cents": s.revenue_cents, "previous_revenue_cents": s.previous_revenue_cents}
            for s in series
        ]
        return _format_csv(rows, f"revenue_by_period_{start_date}_{end_date}.csv")

    return RevenueByPeriodResponse(
        period={"start_date": start_date, "end_date": end_date},
        group_by=group_by,
        series=series,
        total_current_cents=total_current,
        total_previous_cents=total_previous,
        change_cents=change,
        change_percent=change_pct,
    )


@router.get("/payroll-reconciliation", response_model=PayrollReconciliationResponse)
def payroll_reconciliation(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    period: str | None = Query(None),
    format: Literal["json", "csv"] = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    start_date, end_date = _parse_period(start_date, end_date, period)
    org_id = user.organisation_id
    days_in_period = max(1, (end_date - start_date).days + 1)

    employees = db.query(Employee).filter(Employee.organisation_id == org_id).order_by(Employee.hire_date).all()
    packages = {p.id: p for p in db.query(RemunerationPackage).filter(RemunerationPackage.organisation_id == org_id).all()}
    drivers = {d.id: d.name for d in db.query(Driver).filter(Driver.organisation_id == org_id).all()}

    salary_paid_q = db.query(
        SalaryPayment.employee_id,
        func.coalesce(func.sum(SalaryPayment.amount_cents), 0).label("total"),
    ).filter(
        SalaryPayment.organisation_id == org_id,
        SalaryPayment.payment_date >= start_date,
        SalaryPayment.payment_date <= end_date,
    ).group_by(SalaryPayment.employee_id)
    salary_paid_rows = {r.employee_id: r.total for r in salary_paid_q.all()}

    items = []
    for emp in employees:
        driver_name = drivers.get(emp.driver_id, "Unknown")
        pkg = packages.get(emp.remuneration_package_id) if emp.remuneration_package_id else None

        hire = max(emp.hire_date, start_date) if emp.hire_date else start_date
        term = emp.termination_date or end_date
        term = min(term, end_date)
        days_employed = max(0, (term - hire).days + 1)

        salary_owed = 0
        if pkg:
            if pkg.payment_frequency == "weekly":
                salary_owed = int(pkg.base_salary_cents * days_employed / 7)
            else:
                salary_owed = int(pkg.base_salary_cents * days_employed / days_in_period)

        salary_paid = salary_paid_rows.get(emp.id, 0)

        items.append(PayrollItem(
            employee_id=emp.id,
            driver_name=driver_name,
            package_name=pkg.name if pkg else None,
            payment_frequency=pkg.payment_frequency if pkg else None,
            days_employed=days_employed,
            salary_owed_cents=salary_owed,
            salary_paid_cents=salary_paid,
            salary_balance_cents=salary_owed - salary_paid,
            employment_status=emp.employment_status,
        ))

    total_owed = sum(i.salary_owed_cents for i in items)
    total_paid = sum(i.salary_paid_cents for i in items)

    if format == "csv":
        rows = [i.model_dump() for i in items]
        return _format_csv(rows, f"payroll_reconciliation_{start_date}_{end_date}.csv")

    return PayrollReconciliationResponse(
        period={"start_date": start_date, "end_date": end_date},
        items=items,
        total_owed_cents=total_owed,
        total_paid_cents=total_paid,
        total_liability_cents=total_owed - total_paid,
    )


@router.get("/asset-register", response_model=AssetRegisterResponse)
def asset_register(
    format: Literal["json", "csv"] = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    org_id = user.organisation_id
    taxis = db.query(Taxi).filter(Taxi.organisation_id == org_id).all()

    loans = {l.taxi_id: l for l in db.query(TaxiLoan).filter(TaxiLoan.organisation_id == org_id).all()}
    taxis_with_insurance = set(
        r[0] for r in db.query(Insurance.taxi_id).filter(Insurance.organisation_id == org_id).all()
    )

    items = []
    for t in taxis:
        loan = loans.get(t.id)
        purchase_price = loan.total_amount_cents if loan else None
        remaining_balance = loan.remaining_balance_cents if loan else None
        monthly_instalment = loan.monthly_instalment_cents if loan else None

        # Insurance — find latest active policy premium
        insurance_premium = None
        if t.id in taxis_with_insurance:
            pol = db.query(Insurance).filter(
                Insurance.taxi_id == t.id, Insurance.organisation_id == org_id
            ).order_by(Insurance.created_at.desc()).first()
            if pol:
                insurance_premium = pol.monthly_premium_cents

        # Total cost to date
        total_cost = (
            db.query(func.coalesce(func.sum(Fuel.cost_total), 0))
            .filter(Fuel.taxi_id == t.id).scalar() or 0
        )
        total_cost += (
            db.query(func.coalesce(func.sum(Breakdown.cost_total), 0))
            .filter(Breakdown.taxi_id == t.id).scalar() or 0
        )
        total_cost += (
            db.query(func.coalesce(func.sum(SparePartPurchase.cost_total_cents), 0))
            .filter(SparePartPurchase.taxi_id == t.id).scalar() or 0
        )
        total_cost += (
            db.query(func.coalesce(func.sum(MechanicPayment.amount_cents), 0))
            .filter(MechanicPayment.taxi_id == t.id).scalar() or 0
        )
        if loan:
            total_cost += (
                db.query(func.coalesce(func.sum(LoanPayment.amount_cents), 0))
                .filter(LoanPayment.loan_id == loan.id).scalar() or 0
            )

        # Total income to date
        total_income = (
            db.query(func.coalesce(func.sum(DailyIncome.total_cash), 0))
            .filter(DailyIncome.taxi_id == t.id).scalar() or 0
        )

        net_position = total_income - total_cost

        items.append(AssetRegisterItem(
            taxi_id=t.id,
            registration_number=t.registration_number,
            model=t.model,
            status=t.status,
            purchase_price_cents=purchase_price,
            remaining_balance_cents=remaining_balance,
            monthly_instalment_cents=monthly_instalment,
            insurance_premium_cents=insurance_premium,
            total_cost_to_date_cents=total_cost,
            total_income_to_date_cents=total_income,
            net_position_cents=net_position,
        ))

    total_asset_value = sum(i.purchase_price_cents or 0 for i in items)
    total_loan_balance = sum(i.remaining_balance_cents or 0 for i in items)
    total_net = sum(i.net_position_cents for i in items)

    if format == "csv":
        rows = [i.model_dump() for i in items]
        return _format_csv(rows, "asset_register.csv")

    return AssetRegisterResponse(
        items=items,
        total_asset_value_cents=total_asset_value,
        total_loan_balance_cents=total_loan_balance,
        total_net_position_cents=total_net,
    )


@router.get("/loan-schedule", response_model=LoanScheduleResponse)
def loan_schedule(
    format: Literal["json", "csv"] = Query("json"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    import math
    org_id = user.organisation_id

    taxi_map = {t.id: t.registration_number for t in db.query(Taxi).filter(Taxi.organisation_id == org_id).all()}
    loans = db.query(TaxiLoan).filter(TaxiLoan.organisation_id == org_id).order_by(TaxiLoan.created_at.desc()).all()

    items = []
    for loan in loans:
        payments_made = (
            db.query(func.count(LoanPayment.id))
            .filter(LoanPayment.loan_id == loan.id)
            .scalar()
        ) or 0
        total_paid = (
            db.query(func.coalesce(func.sum(LoanPayment.amount_cents), 0))
            .filter(LoanPayment.loan_id == loan.id)
            .scalar()
        ) or 0

        remaining_payments = 0
        projected_pay_off = None
        if loan.monthly_instalment_cents and loan.monthly_instalment_cents > 0:
            remaining_payments = math.ceil(loan.remaining_balance_cents / loan.monthly_instalment_cents)

            # Get last payment date + remaining months
            last_payment = db.query(func.max(LoanPayment.payment_date)).filter(
                LoanPayment.loan_id == loan.id
            ).scalar()
            if last_payment:
                mp = last_payment.month + remaining_payments
                yr = last_payment.year + (mp - 1) // 12
                mo = ((mp - 1) % 12) + 1
                projected_pay_off = date(yr, mo, 1)
            else:
                # No payments yet — project from start date
                created = loan.created_at.date() if hasattr(loan.created_at, 'date') else loan.created_at
                mp = created.month + remaining_payments
                yr = created.year + (mp - 1) // 12
                mo = ((mp - 1) % 12) + 1
                projected_pay_off = date(yr, mo, 1)

        items.append(LoanScheduleItem(
            loan_id=loan.id,
            taxi_registration=taxi_map.get(loan.taxi_id, "Unknown"),
            total_amount_cents=loan.total_amount_cents,
            remaining_balance_cents=loan.remaining_balance_cents,
            monthly_instalment_cents=loan.monthly_instalment_cents,
            payments_made=payments_made,
            total_paid_to_date_cents=total_paid,
            remaining_payments=remaining_payments,
            projected_pay_off_date=projected_pay_off,
        ))

    total_outstanding = sum(i.remaining_balance_cents for i in items)
    total_original = sum(i.total_amount_cents for i in items)
    total_paid = sum(i.total_paid_to_date_cents for i in items)

    if format == "csv":
        rows = [i.model_dump() for i in items]
        return _format_csv(rows, "loan_schedule.csv")

    return LoanScheduleResponse(
        items=items,
        total_outstanding_cents=total_outstanding,
        total_original_cents=total_original,
        total_paid_cents=total_paid,
    )
