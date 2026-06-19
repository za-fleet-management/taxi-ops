import logging
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api import api_router
from app.api.deps import get_current_user, get_optional_user, require_accountant_or_above, require_owner

logger = logging.getLogger(__name__)
from app.api.reporting import (
    asset_register as asset_register_endpoint,
    balance_sheet as balance_sheet_endpoint,
    cash_flow as cash_flow_endpoint,
    depot_costs as depot_costs_endpoint,
    driver_performance_report as driver_performance_endpoint,
    executive_summary as executive_summary_endpoint,
    fixed_vs_variable as fixed_vs_variable_endpoint,
    income_statement as income_statement_endpoint,
    loan_schedule as loan_schedule_endpoint,
    maintenance_downtime as maintenance_downtime_endpoint,
    payroll_reconciliation as payroll_reconciliation_endpoint,
    revenue_by_period as revenue_by_period_endpoint,
    route_profitability_report as route_profitability_endpoint,
    taxi_profitability as taxi_profitability_endpoint,
)
from app.api.admin import admin_dashboard as admin_dashboard_endpoint
from app.api.reports import cost_of_operations as cost_of_operations_endpoint
from app.seed import seed_status as seed_status_endpoint
from app.database import get_db
from app.models.breakdown import Breakdown
from app.models.depot import Depot
from app.models.driver import Driver
from app.models.employee import Employee
from app.models.fuel import Fuel
from app.models.income import DailyIncome
from app.models.insurance import Insurance
from app.models.mechanic_payment import MechanicPayment
from app.models.remuneration import RemunerationPackage
from app.models.route import Route, RouteAssignment
from app.models.salary_payment import SalaryPayment
from app.models.spare_part import SparePartPurchase
from app.models.organisation import Organisation
from app.models.subscription import OrganisationSubscription, SubscriptionPayment
from app.models.taxi import Taxi
from app.models.taxi_loan import LoanPayment, TaxiLoan
from app.models.user import User

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import SessionLocal
    from app.seed_admin import seed_admin
    db = SessionLocal()
    try:
        if seed_admin(db):
            logger.info("=" * 60)
            logger.info("Superadmin account created!")
            logger.info("  Phone: mobiusndou@gmail.com")
            logger.info("  Password: Mobius5627084@")
            logger.info("  URL: http://localhost:8000/login")
            logger.info("=" * 60)
    except Exception as e:
        logger.warning("Could not seed admin: %s", e)
    finally:
        db.close()
    yield


app = FastAPI(title="TaxiOps", lifespan=lifespan)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(api_router)


@app.middleware("http")
async def subscription_banner_middleware(request: Request, call_next):
    request.state.sub_expired = False
    request.state.subscription_org_id = None
    token = request.cookies.get("access_token")
    if token:
        from app.config import settings
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            org_id = payload.get("organisation_id")
            if org_id:
                from app.database import SessionLocal
                db = SessionLocal()
                try:
                    sub = db.query(OrganisationSubscription).filter(
                        OrganisationSubscription.organisation_id == org_id,
                    ).first()
                    if sub and sub.period_end < date.today():
                        request.state.sub_expired = True
                        request.state.subscription_org_id = org_id
                finally:
                    db.close()
        except JWTError:
            pass
    response = await call_next(request)
    return response


@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    user: User | None = Depends(get_optional_user),
):
    return templates.TemplateResponse(
        request,
        "base.html" if user else "landing.html",
        {"request": request, "user": user},
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request})


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse(request, "signup.html", {"request": request})


@app.get("/accept-invite", response_class=HTMLResponse)
def accept_invite_page(request: Request, token: str):
    return templates.TemplateResponse(
        request, "accept_invite.html", {"request": request, "token": token}
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    user: User = Depends(get_current_user),
):
    today = date.today()
    return templates.TemplateResponse(
        request, "dashboard.html", {"request": request, "user": user, "today": today}
    )


@app.get("/taxis", response_class=HTMLResponse)
def taxis_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    routes = db.query(Route).filter(Route.organisation_id == user.organisation_id).all()
    return templates.TemplateResponse(
        request, "taxis.html", {"request": request, "user": user, "routes": routes}
    )


@app.get("/drivers", response_class=HTMLResponse)
def drivers_page(
    request: Request,
    user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request, "drivers.html", {"request": request, "user": user}
    )


@app.get("/income/new", response_class=HTMLResponse)
def income_new_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    taxis = db.query(Taxi).filter(Taxi.organisation_id == user.organisation_id).all()
    drivers = db.query(Driver).filter(Driver.organisation_id == user.organisation_id).all()
    routes = db.query(Route).filter(Route.organisation_id == user.organisation_id).all()
    taxi_route_map = {t.id: t.assigned_route_id for t in taxis}
    return templates.TemplateResponse(
        request,
        "income_new.html",
        {"request": request, "user": user, "taxis": taxis, "drivers": drivers, "routes": routes, "taxi_route_map": taxi_route_map},
    )


@app.get("/breakdowns/new", response_class=HTMLResponse)
def breakdown_new_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    taxis = db.query(Taxi).filter(Taxi.organisation_id == user.organisation_id).all()
    return templates.TemplateResponse(
        request,
        "breakdowns_new.html",
        {"request": request, "user": user, "taxis": taxis},
    )


@app.get("/fuel/new", response_class=HTMLResponse)
def fuel_new_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    taxis = db.query(Taxi).filter(Taxi.organisation_id == user.organisation_id).all()
    return templates.TemplateResponse(
        request,
        "fuel_new.html",
        {"request": request, "user": user, "taxis": taxis},
    )


@app.get("/routes", response_class=HTMLResponse)
def routes_page(
    request: Request,
    user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request, "routes.html", {"request": request, "user": user}
    )


@app.get("/features", response_class=HTMLResponse)
def features_page(request: Request):
    return templates.TemplateResponse(request, "features.html", {"request": request})


@app.get("/about", response_class=HTMLResponse)
def about_page(request: Request):
    return templates.TemplateResponse(request, "about.html", {"request": request})


@app.get("/pricing", response_class=HTMLResponse)
def pricing_page(request: Request):
    return templates.TemplateResponse(request, "pricing.html", {"request": request})


@app.get("/support", response_class=HTMLResponse)
def support_page(request: Request):
    return templates.TemplateResponse(request, "support.html", {"request": request})


@app.get("/reports", response_class=HTMLResponse)
def reports_page(
    request: Request,
    user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request, "reports.html", {"request": request, "user": user}
    )


@app.get("/reports/executive-summary", response_class=HTMLResponse)
def executive_summary_page(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    period: str | None = None,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    data = executive_summary_endpoint(
        start_date=start_date, end_date=end_date, period=period, db=db, user=user
    )
    return templates.TemplateResponse(
        request, "reports/executive_summary.html", {"request": request, "user": user, "data": data, "trend_json": [t.model_dump() for t in data.trend]}
    )


@app.get("/reports/income-statement", response_class=HTMLResponse)
def income_statement_page(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    period: str | None = None,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    data = income_statement_endpoint(
        start_date=start_date, end_date=end_date, period=period, db=db, user=user
    )
    return templates.TemplateResponse(
        request, "reports/income_statement.html", {"request": request, "user": user, "data": data}
    )


@app.get("/reports/cash-flow", response_class=HTMLResponse)
def cash_flow_page(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    period: str | None = None,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    data = cash_flow_endpoint(
        start_date=start_date, end_date=end_date, period=period, db=db, user=user
    )
    return templates.TemplateResponse(
        request, "reports/cash_flow.html", {"request": request, "user": user, "data": data}
    )


@app.get("/reports/balance-sheet", response_class=HTMLResponse)
def balance_sheet_page(
    request: Request,
    as_at: date | None = None,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    data = balance_sheet_endpoint(as_at=as_at, db=db, user=user)
    return templates.TemplateResponse(
        request, "reports/balance_sheet.html", {"request": request, "user": user, "data": data}
    )


@app.get("/reports/taxi-profitability", response_class=HTMLResponse)
def taxi_profitability_page(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    period: str | None = None,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    data = taxi_profitability_endpoint(
        start_date=start_date, end_date=end_date, period=period, taxi_id=None, format="json", db=db, user=user
    )
    return templates.TemplateResponse(
        request, "reports/taxi_profitability.html", {"request": request, "user": user, "data": data, "items_json": [i.model_dump() for i in data.items]}
    )


@app.get("/reports/driver-performance", response_class=HTMLResponse)
def driver_performance_page(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    period: str | None = None,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    data = driver_performance_endpoint(
        start_date=start_date, end_date=end_date, period=period, driver_id=None, format="json", db=db, user=user
    )
    return templates.TemplateResponse(
        request, "reports/driver_performance.html", {"request": request, "user": user, "data": data}
    )


@app.get("/reports/route-profitability", response_class=HTMLResponse)
def route_profitability_page(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    period: str | None = None,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    data = route_profitability_endpoint(
        start_date=start_date, end_date=end_date, period=period, route_id=None, format="json", db=db, user=user
    )
    return templates.TemplateResponse(
        request, "reports/route_profitability.html", {"request": request, "user": user, "data": data}
    )


@app.get("/reports/depot-costs", response_class=HTMLResponse)
def depot_costs_page(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    period: str | None = None,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    data = depot_costs_endpoint(
        start_date=start_date, end_date=end_date, period=period, depot_id=None, format="json", db=db, user=user
    )
    return templates.TemplateResponse(
        request, "reports/depot_costs.html", {"request": request, "user": user, "data": data}
    )


@app.get("/reports/maintenance-downtime", response_class=HTMLResponse)
def maintenance_downtime_page(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    period: str | None = None,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    data = maintenance_downtime_endpoint(
        start_date=start_date, end_date=end_date, period=period, taxi_id=None, format="json", db=db, user=user
    )
    return templates.TemplateResponse(
        request, "reports/maintenance_downtime.html", {"request": request, "user": user, "data": data}
    )


@app.get("/reports/fixed-vs-variable", response_class=HTMLResponse)
def fixed_vs_variable_page(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    period: str | None = None,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    data = fixed_vs_variable_endpoint(
        start_date=start_date, end_date=end_date, period=period, db=db, user=user
    )
    return templates.TemplateResponse(
        request, "reports/fixed_vs_variable.html", {"request": request, "user": user, "data": data, "items_json": [i.model_dump() for i in data.items]}
    )


@app.get("/reports/revenue-by-period", response_class=HTMLResponse)
def revenue_by_period_page(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    period: str | None = None,
    group_by: str = "month",
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    data = revenue_by_period_endpoint(
        start_date=start_date, end_date=end_date, period=period, group_by=group_by, db=db, user=user
    )
    return templates.TemplateResponse(
        request, "reports/revenue_by_period.html", {"request": request, "user": user, "data": data, "series_json": [s.model_dump() for s in data.series]}
    )


@app.get("/reports/payroll-reconciliation", response_class=HTMLResponse)
def payroll_reconciliation_page(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    period: str | None = None,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    data = payroll_reconciliation_endpoint(
        start_date=start_date, end_date=end_date, period=period, db=db, user=user
    )
    return templates.TemplateResponse(
        request, "reports/payroll_reconciliation.html", {"request": request, "user": user, "data": data, "items_json": [i.model_dump() for i in data.items]}
    )


@app.get("/reports/asset-register", response_class=HTMLResponse)
def asset_register_page(
    request: Request,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    data = asset_register_endpoint(db=db, user=user)
    return templates.TemplateResponse(
        request, "reports/asset_register.html", {"request": request, "user": user, "data": data, "items_json": [i.model_dump() for i in data.items]}
    )


@app.get("/reports/loan-schedule", response_class=HTMLResponse)
def loan_schedule_page(
    request: Request,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    data = loan_schedule_endpoint(db=db, user=user)
    return templates.TemplateResponse(
        request, "reports/loan_schedule.html", {"request": request, "user": user, "data": data, "items_json": [i.model_dump(mode="json") for i in data.items]}
    )


@app.get("/users", response_class=HTMLResponse)
def users_page(
    request: Request,
    user: User = Depends(require_owner),
):
    return templates.TemplateResponse(
        request, "users.html", {"request": request, "user": user}
    )


@app.get("/subscription", response_class=HTMLResponse)
def subscription_page(
    request: Request,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    from datetime import date as d8
    today = d8.today()

    sub = db.query(OrganisationSubscription).filter(
        OrganisationSubscription.organisation_id == user.organisation_id,
    ).first()

    taxi_count = (
        db.query(Taxi)
        .filter(Taxi.organisation_id == user.organisation_id, Taxi.status == "active")
        .count()
    )

    payments = (
        db.query(SubscriptionPayment)
        .filter(SubscriptionPayment.organisation_id == user.organisation_id)
        .order_by(SubscriptionPayment.created_at.desc())
        .all()
    )

    from app.config import settings

    sub_data = None
    if sub:
        sub_data = {
            "id": sub.id,
            "plan_months": sub.plan_months,
            "price_per_taxi_cents": sub.price_per_taxi_cents,
            "taxi_count": sub.taxi_count,
            "total_amount_cents": sub.total_amount_cents,
            "period_start": sub.period_start,
            "period_end": sub.period_end,
            "status": sub.status,
            "expired": sub.period_end < today,
            "days_remaining": (sub.period_end - today).days,
        }
        if sub_data["expired"]:
            sub_data["days_remaining"] = 0

    bank = {
        "name": settings.bank_name,
        "account_holder": settings.bank_account_holder,
        "account_number": settings.bank_account_number,
        "branch_code": settings.bank_branch_code,
    }

    return templates.TemplateResponse(
        request,
        "subscription.html",
        {
            "request": request,
            "user": user,
            "sub": sub_data,
            "taxi_count": taxi_count,
            "payments": payments,
            "bank": bank,
            "today": today.isoformat(),
        },
    )


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse(request, "admin_login.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
def admin_page(
    request: Request,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    ctx = {"request": request, "user": user}
    if user.role == "superadmin":
        ctx["orgs"] = db.query(Organisation).order_by(Organisation.name).all()
    return templates.TemplateResponse(request, "admin.html", ctx)


@app.get("/partials/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard_partial(
    request: Request,
    org_id: str | None = None,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    data = admin_dashboard_endpoint(db=db, user=user, org_id=effective_org_id)
    return templates.TemplateResponse(
        request,
        "partials/admin/_dashboard_content.html",
        {"request": request, "data": data, "org_id": effective_org_id},
    )


@app.get("/partials/admin/settings", response_class=HTMLResponse)
def admin_settings_partial(
    request: Request,
    org_id: str | None = None,
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    return templates.TemplateResponse(
        request,
        "partials/admin/settings.html",
        {"request": request, "user": user, "org_id": effective_org_id},
    )


@app.get("/partials/admin/billing", response_class=HTMLResponse)
def admin_billing_partial(
    request: Request,
    org_id: str | None = None,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    from app.config import settings

    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    taxi_count = (
        db.query(Taxi)
        .filter(Taxi.organisation_id == effective_org_id, Taxi.status == "active")
        .count()
    )

    return templates.TemplateResponse(
        request,
        "partials/admin/billing.html",
        {
            "request": request,
            "user": user,
            "org_id": effective_org_id,
            "taxi_count": taxi_count,
            "bank": {
                "name": settings.bank_name,
                "account_holder": settings.bank_account_holder,
                "account_number": settings.bank_account_number,
                "branch_code": settings.bank_branch_code,
            },
        },
    )


@app.get("/partials/admin/reconciliation", response_class=HTMLResponse)
def admin_reconciliation_partial(
    request: Request,
    org_id: str | None = None,
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    return templates.TemplateResponse(
        request,
        "partials/admin/reconciliation.html",
        {"request": request, "user": user, "org_id": effective_org_id},
    )


@app.get("/partials/admin/invoices", response_class=HTMLResponse)
def admin_invoices_partial(
    request: Request,
    org_id: str | None = None,
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    return templates.TemplateResponse(
        request,
        "partials/admin/invoices.html",
        {"request": request, "user": user, "org_id": effective_org_id},
    )


@app.get("/partials/admin/audit-log", response_class=HTMLResponse)
def admin_audit_log_partial(
    request: Request,
    org_id: str | None = None,
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    return templates.TemplateResponse(
        request,
        "partials/admin/audit_log.html",
        {"request": request, "user": user, "org_id": effective_org_id},
    )


@app.get("/partials/admin/demo-data", response_class=HTMLResponse)
def admin_demo_data_partial(
    request: Request,
    org_id: str | None = None,
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    return templates.TemplateResponse(
        request,
        "partials/admin/demo_data.html",
        {"request": request, "user": user, "org_id": effective_org_id},
    )


@app.get("/admin/dashboard-data")
def admin_dashboard_data(
    org_id: str | None = None,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    return admin_dashboard_endpoint(db=db, user=user, org_id=effective_org_id)


@app.get("/remuneration", response_class=HTMLResponse)
def remuneration_page(
    request: Request,
    user: User = Depends(require_owner),
):
    return templates.TemplateResponse(
        request, "remuneration.html", {"request": request, "user": user}
    )


@app.get("/employees", response_class=HTMLResponse)
def employees_page(
    request: Request,
    user: User = Depends(require_accountant_or_above),
):
    return templates.TemplateResponse(
        request, "employees.html", {"request": request, "user": user}
    )


@app.get("/employees/{employee_id}/payments", response_class=HTMLResponse)
def employee_payments_page(
    request: Request,
    employee_id: str,
    user: User = Depends(require_accountant_or_above),
    db: Session = Depends(get_db),
):
    emp = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.organisation_id == user.organisation_id,
    ).first()
    if not emp:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/employees", status_code=302)
    driver = db.query(Driver).filter(Driver.id == emp.driver_id).first()
    pkg = None
    if emp.remuneration_package_id:
        pkg = db.query(RemunerationPackage).filter(
            RemunerationPackage.id == emp.remuneration_package_id
        ).first()
    return templates.TemplateResponse(
        request,
        "employee_payments.html",
        {"request": request, "user": user, "employee": emp, "driver": driver, "package": pkg},
    )


@app.get("/salary/new", response_class=HTMLResponse)
def salary_new_page(
    request: Request,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    employees = (
        db.query(Employee)
        .filter(
            Employee.organisation_id == user.organisation_id,
            Employee.employment_status == "active",
        )
        .all()
    )
    emp_details = []
    for e in employees:
        driver = db.query(Driver).filter(Driver.id == e.driver_id).first()
        emp_details.append({
            "id": e.id,
            "driver_name": driver.name if driver else "Unknown",
        })
    return templates.TemplateResponse(
        request,
        "salary_new.html",
        {"request": request, "user": user, "employees": emp_details},
    )


@app.get("/depots", response_class=HTMLResponse)
def depots_page(
    request: Request,
    user: User = Depends(require_owner),
):
    return templates.TemplateResponse(request, "depots.html", {"request": request, "user": user})


@app.get("/insurance", response_class=HTMLResponse)
def insurance_page(
    request: Request,
    user: User = Depends(require_owner),
):
    return templates.TemplateResponse(request, "insurance.html", {"request": request, "user": user})


@app.get("/loans", response_class=HTMLResponse)
def loans_page(
    request: Request,
    user: User = Depends(require_owner),
):
    return templates.TemplateResponse(request, "loans.html", {"request": request, "user": user})


@app.get("/loans/{loan_id}/payments", response_class=HTMLResponse)
def loan_payments_page(
    request: Request,
    loan_id: str,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    loan = db.query(TaxiLoan).filter(
        TaxiLoan.id == loan_id,
        TaxiLoan.organisation_id == user.organisation_id,
    ).first()
    if not loan:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/loans", status_code=302)
    taxi = db.query(Taxi).filter(Taxi.id == loan.taxi_id).first()
    return templates.TemplateResponse(
        request,
        "loan_payments.html",
        {"request": request, "user": user, "loan": loan, "taxi": taxi},
    )


@app.get("/spare-parts/new", response_class=HTMLResponse)
def spare_parts_new_page(
    request: Request,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    depots = db.query(Depot).filter(Depot.organisation_id == user.organisation_id).all()
    taxis = db.query(Taxi).filter(Taxi.organisation_id == user.organisation_id).all()
    return templates.TemplateResponse(
        request,
        "spare_parts_new.html",
        {"request": request, "user": user, "depots": depots, "taxis": taxis},
    )


@app.get("/mechanic-payments/new", response_class=HTMLResponse)
def mechanic_payments_new_page(
    request: Request,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    depots = db.query(Depot).filter(Depot.organisation_id == user.organisation_id).all()
    taxis = db.query(Taxi).filter(Taxi.organisation_id == user.organisation_id).all()
    return templates.TemplateResponse(
        request,
        "mechanic_payments_new.html",
        {"request": request, "user": user, "depots": depots, "taxis": taxis},
    )


# ── Dashboard summary endpoints (any authenticated user) ──────────────────


@app.get("/api/dashboard/summary")
def dashboard_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    taxis = db.query(Taxi).filter(Taxi.organisation_id == user.organisation_id).all()
    drivers = db.query(Driver).filter(Driver.organisation_id == user.organisation_id).all()

    today = date.today()
    month_start = today.replace(day=1)
    income_total = (
        db.query(func.coalesce(func.sum(DailyIncome.total_cash), 0))
        .filter(
            DailyIncome.organisation_id == user.organisation_id,
            DailyIncome.date >= month_start,
            DailyIncome.date <= today,
        )
        .scalar()
    )
    open_breakdowns = (
        db.query(func.count(Breakdown.id))
        .filter(
            Breakdown.organisation_id == user.organisation_id,
            Breakdown.end_time.is_(None),
        )
        .scalar()
    )

    return {
        "active_taxis": sum(1 for t in taxis if t.status == "active"),
        "total_taxis": len(taxis),
        "active_drivers": sum(1 for d in drivers if d.status == "active"),
        "total_drivers": len(drivers),
        "income_this_month": income_total,
        "open_breakdowns": open_breakdowns,
    }


# ── HTML fragment endpoints for htmx ─────────────────────────────────────


@app.get("/partials/taxis", response_class=HTMLResponse)
def taxi_rows(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    taxis = db.query(Taxi).filter(Taxi.organisation_id == user.organisation_id).all()
    routes = db.query(Route).filter(Route.organisation_id == user.organisation_id).all()
    route_map = {r.id: r.name for r in routes}
    return templates.TemplateResponse(
        request,
        "partials/_taxi_rows.html",
        {"request": request, "user": user, "taxis": taxis, "routes": routes, "route_map": route_map},
    )


@app.get("/partials/drivers", response_class=HTMLResponse)
def driver_rows(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    drivers = db.query(Driver).filter(Driver.organisation_id == user.organisation_id).all()
    taxis = db.query(Taxi).filter(Taxi.organisation_id == user.organisation_id).all()
    taxi_map = {t.id: t.registration_number for t in taxis}
    return templates.TemplateResponse(
        request,
        "partials/_driver_rows.html",
        {"request": request, "user": user, "drivers": drivers, "taxis": taxis, "taxi_map": taxi_map},
    )


@app.get("/partials/routes", response_class=HTMLResponse)
def route_rows(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    routes = db.query(Route).filter(Route.organisation_id == user.organisation_id).all()
    return templates.TemplateResponse(
        request,
        "partials/_route_rows.html",
        {"request": request, "user": user, "routes": routes},
    )


@app.get("/partials/users", response_class=HTMLResponse)
def user_rows(
    request: Request,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    from app.models.user import User as UserModel

    users = (
        db.query(UserModel)
        .filter(
            UserModel.organisation_id == user.organisation_id,
            UserModel.id != user.id,
        )
        .order_by(UserModel.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "partials/_user_rows.html",
        {"request": request, "user": user, "users": users},
    )


@app.get("/partials/income/recent", response_class=HTMLResponse)
def recent_income_rows(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if start_date is None:
        start_date = date.today()
    if end_date is None:
        end_date = date.today()

    rows = (
        db.query(
            DailyIncome.id,
            DailyIncome.date,
            DailyIncome.total_cash,
            DailyIncome.notes,
            Taxi.registration_number.label("taxi_registration"),
            Driver.name.label("driver_name"),
        )
        .join(Taxi, DailyIncome.taxi_id == Taxi.id)
        .join(Driver, DailyIncome.driver_id == Driver.id)
        .filter(
            DailyIncome.organisation_id == user.organisation_id,
            DailyIncome.date >= start_date,
            DailyIncome.date <= end_date,
        )
        .order_by(DailyIncome.date.desc())
        .all()
    )

    incomes = [
        {
            "date": r.date,
            "total_cash": r.total_cash,
            "notes": r.notes,
            "taxi_registration": r.taxi_registration,
            "driver_name": r.driver_name,
        }
        for r in rows
    ]
    return templates.TemplateResponse(
        request,
        "partials/_income_rows.html",
        {"request": request, "user": user, "incomes": incomes},
    )


@app.get("/partials/reports/income-summary", response_class=HTMLResponse)
def report_income_summary_html(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(
        DailyIncome.date,
        Route.name.label("route_name"),
        func.sum(DailyIncome.total_cash).label("total_cash"),
        func.count(DailyIncome.id).label("entry_count"),
    ).outerjoin(
        RouteAssignment, RouteAssignment.daily_income_id == DailyIncome.id,
    ).outerjoin(
        Route, Route.id == RouteAssignment.route_id,
    ).filter(DailyIncome.organisation_id == user.organisation_id)

    if start_date:
        q = q.filter(DailyIncome.date >= start_date)
    if end_date:
        q = q.filter(DailyIncome.date <= end_date)

    q = q.group_by(DailyIncome.date, Route.name).order_by(DailyIncome.date)
    rows = q.all()

    items = [{"date": r.date, "route_name": r.route_name or "—", "total_cash": r.total_cash, "entry_count": r.entry_count} for r in rows]
    grand_total = sum(r.total_cash for r in rows)
    return templates.TemplateResponse(
        request,
        "partials/_report_income_summary.html",
        {"request": request, "items": items, "grand_total": grand_total},
    )


@app.get("/partials/reports/driver-performance", response_class=HTMLResponse)
def report_driver_performance_html(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_id = user.organisation_id
    income_q = db.query(
        DailyIncome.driver_id,
        func.sum(DailyIncome.total_cash).label("total_income"),
        func.count(DailyIncome.id).label("income_days"),
    ).filter(DailyIncome.organisation_id == org_id)

    if start_date:
        income_q = income_q.filter(DailyIncome.date >= start_date)
    if end_date:
        income_q = income_q.filter(DailyIncome.date <= end_date)

    income_rows = {r.driver_id: r for r in income_q.group_by(DailyIncome.driver_id).all()}

    drivers = db.query(Driver).filter(Driver.organisation_id == org_id, Driver.status == "active").all()

    if start_date is None:
        start_date = db.query(func.min(DailyIncome.date)).filter(DailyIncome.organisation_id == org_id).scalar() or date.today()
    if end_date is None:
        end_date = date.today()
    total_calendar_days = (end_date - start_date).days + 1

    taxi_route_map = {}
    taxis = db.query(Taxi).filter(Taxi.organisation_id == org_id).all()
    for t in taxis:
        if t.assigned_route_id:
            route = db.query(Route).filter(Route.id == t.assigned_route_id).first()
            if route:
                taxi_route_map[t.id] = route.name

    driver_taxi_map = {}
    for d in drivers:
        if d.assigned_taxi_id and d.assigned_taxi_id in taxi_route_map:
            driver_taxi_map[d.id] = taxi_route_map[d.assigned_taxi_id]

    items = []
    for d in drivers:
        inc = income_rows.get(d.id)
        total_income = inc.total_income if inc else 0
        income_days = inc.income_days if inc else 0
        idle_days = max(0, total_calendar_days - income_days)
        items.append({
            "driver_name": d.name,
            "total_income_cents": total_income,
            "income_days": income_days,
            "idle_days": idle_days,
            "route_name": driver_taxi_map.get(d.id, "—"),
        })

    return templates.TemplateResponse(
        request,
        "partials/_report_driver_performance.html",
        {"request": request, "items": items},
    )


@app.get("/partials/reports/downtime-cost", response_class=HTMLResponse)
def report_downtime_cost_html(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(
        Breakdown.id,
        Breakdown.taxi_id,
        Taxi.registration_number,
        Taxi.assigned_route_id,
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
    q = q.order_by(Breakdown.start_time.desc())

    route_ids = {row.assigned_route_id for row in q.all() if row.assigned_route_id}
    route_map = {}
    if route_ids:
        routes = db.query(Route).filter(Route.id.in_(route_ids)).all()
        route_map = {r.id: r.name for r in routes}

    total_cost = 0
    items = []
    for row in q.all():
        cost = row.cost_total or 0
        total_cost += cost
        duration = timedelta()
        if row.end_time:
            duration = row.end_time - row.start_time
        items.append({
            "registration_number": row.registration_number,
            "route_name": route_map.get(row.assigned_route_id, "—"),
            "start_time": row.start_time,
            "end_time": row.end_time,
            "duration_hours": duration.total_seconds() / 3600,
            "cost_total": row.cost_total,
        })

    return templates.TemplateResponse(
        request,
        "partials/_report_downtime_cost.html",
        {"request": request, "items": items, "total_cost": total_cost},
    )


@app.get("/partials/reports/cost-of-operations", response_class=HTMLResponse)
def report_cost_of_operations_html(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response = cost_of_operations_endpoint(start_date=start_date, end_date=end_date, db=db, user=user)
    items = [item.model_dump() for item in response.items]
    return templates.TemplateResponse(
        request,
        "partials/_report_cost_of_operations.html",
        {"request": request, "items": items},
    )


@app.get("/partials/reports/route-profitability", response_class=HTMLResponse)
def report_route_profitability_html(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
    income_q = income_q.group_by(Route.id, Route.name, Route.distance_km)
    route_data = income_q.all()

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
        items.append({
            "route_name": r.route_name,
            "distance_km": r.distance_km,
            "total_income": r.total_income,
            "allocated_costs": allocated_costs,
            "profit": r.total_income - allocated_costs,
        })

    return templates.TemplateResponse(
        request,
        "partials/_report_route_profitability.html",
        {"request": request, "items": items},
    )


# ── Employee / Remuneration / Salary partials ────────────────────────────


@app.get("/partials/employees", response_class=HTMLResponse)
def employee_rows(
    request: Request,
    user: User = Depends(require_accountant_or_above),
    db: Session = Depends(get_db),
):
    employees = (
        db.query(Employee)
        .filter(Employee.organisation_id == user.organisation_id)
        .order_by(Employee.created_at.desc())
        .all()
    )
    details = []
    for e in employees:
        driver = db.query(Driver).filter(Driver.id == e.driver_id).first()
        pkg = None
        if e.remuneration_package_id:
            pkg = db.query(RemunerationPackage).filter(
                RemunerationPackage.id == e.remuneration_package_id
            ).first()
        depot = None
        if e.depot_id:
            depot = db.query(Depot).filter(Depot.id == e.depot_id).first()
        details.append({
            "employee": e,
            "driver_name": driver.name if driver else "Unknown",
            "driver_phone": driver.phone if driver else "",
            "package_name": pkg.name if pkg else None,
            "base_salary_cents": pkg.base_salary_cents if pkg else None,
            "payment_frequency": pkg.payment_frequency if pkg else None,
            "depot_id": e.depot_id,
            "depot_name": depot.name if depot else None,
        })
    return templates.TemplateResponse(
        request,
        "partials/_employee_rows.html",
        {"request": request, "user": user, "employees": details},
    )


@app.get("/partials/remuneration", response_class=HTMLResponse)
def remuneration_rows(
    request: Request,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    packages = (
        db.query(RemunerationPackage)
        .filter(RemunerationPackage.organisation_id == user.organisation_id)
        .order_by(RemunerationPackage.name)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "partials/_remuneration_rows.html",
        {"request": request, "packages": packages},
    )


@app.get("/partials/salary-payments", response_class=HTMLResponse)
def salary_payment_rows(
    request: Request,
    employee_id: str | None = None,
    user: User = Depends(require_accountant_or_above),
    db: Session = Depends(get_db),
):
    q = (
        db.query(SalaryPayment, Driver.name.label("driver_name"))
        .join(Employee, Employee.id == SalaryPayment.employee_id)
        .join(Driver, Driver.id == Employee.driver_id)
        .filter(SalaryPayment.organisation_id == user.organisation_id)
    )
    if employee_id:
        q = q.filter(SalaryPayment.employee_id == employee_id)
    rows = q.order_by(SalaryPayment.payment_date.desc()).all()

    payments = []
    for p, driver_name in rows:
        payments.append({
            "id": p.id,
            "driver_name": driver_name,
            "amount_cents": p.amount_cents,
            "payment_date": p.payment_date,
            "payment_method": p.payment_method,
            "reference": p.reference,
        })

    return templates.TemplateResponse(
        request,
        "partials/_salary_payment_rows.html",
        {"request": request, "payments": payments},
    )


# ── Depots / Insurance / Loans / Spare Parts / Mechanic partials ─────────


@app.get("/partials/depots", response_class=HTMLResponse)
def depot_rows(
    request: Request,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    depots = db.query(Depot).filter(Depot.organisation_id == user.organisation_id).order_by(Depot.name).all()
    return templates.TemplateResponse(
        request,
        "partials/_depot_rows.html",
        {"request": request, "depots": depots},
    )


@app.get("/partials/insurance", response_class=HTMLResponse)
def insurance_rows(
    request: Request,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(
            Insurance,
            Taxi.registration_number.label("registration_number"),
        )
        .join(Taxi, Taxi.id == Insurance.taxi_id)
        .filter(Insurance.organisation_id == user.organisation_id)
        .order_by(Insurance.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "partials/_insurance_rows.html",
        {"request": request, "insurances": [(i, reg) for i, reg in rows]},
    )


@app.get("/partials/loans", response_class=HTMLResponse)
def loan_rows(
    request: Request,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    loans = db.query(TaxiLoan).filter(TaxiLoan.organisation_id == user.organisation_id).order_by(TaxiLoan.created_at.desc()).all()
    taxi_map = {t.id: t.registration_number for t in db.query(Taxi).filter(Taxi.organisation_id == user.organisation_id).all()}
    return templates.TemplateResponse(
        request,
        "partials/_loan_rows.html",
        {"request": request, "loans": loans, "taxi_map": taxi_map},
    )


@app.get("/partials/loans/{loan_id}/payments", response_class=HTMLResponse)
def loan_payment_rows(
    request: Request,
    loan_id: str,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    loan = db.query(TaxiLoan).filter(
        TaxiLoan.id == loan_id,
        TaxiLoan.organisation_id == user.organisation_id,
    ).first()
    if not loan:
        return templates.TemplateResponse(
            request,
            "partials/_loan_payment_rows.html",
            {"request": request, "payments": []},
        )
    payments = db.query(LoanPayment).filter(
        LoanPayment.loan_id == loan_id,
        LoanPayment.organisation_id == user.organisation_id,
    ).order_by(LoanPayment.payment_date.desc()).all()
    return templates.TemplateResponse(
        request,
        "partials/_loan_payment_rows.html",
        {"request": request, "payments": payments},
    )
