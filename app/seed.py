"""Seeds a fresh organisation with realistic South African taxi fleet demo data."""

import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.breakdown import Breakdown
from app.models.depot import Depot
from app.models.driver import Driver
from app.models.employee import Employee
from app.models.fuel import Fuel
from app.models.income import DailyIncome
from app.models.insurance import Insurance
from app.models.mechanic_payment import MechanicPayment
from app.models.notification import Notification
from app.models.remuneration import RemunerationPackage
from app.models.route import Route, RouteAssignment
from app.models.salary_payment import SalaryPayment
from app.models.spare_part import SparePartPurchase
from app.models.taxi import Taxi
from app.models.taxi_loan import LoanPayment, TaxiLoan

random.seed(42)

# ── Realistic SA taxi fleet data ──────────────────────────────────────────

TAXIS = [
    ("CF 123-45", "Toyota Quantum 2.7i", "active"),
    ("CF 678-90", "Toyota Hiace 3.0D", "active"),
    ("CY 111-22", "Nissan NP200 1.6", "active"),
    ("CA 333-44", "Ford Ranger 2.2 TDCi", "active"),
    ("CF 555-66", "Toyota Corolla 1.8", "active"),
    ("CY 777-88", "Volkswagen Caravelle 2.0 TDI", "active"),
    ("CA 999-00", "Hyundai H-1 2.5 CRDi", "active"),
]

DRIVERS = [
    ("Thabo Molefe", "072 123 4567", "active"),
    ("Lindiwe Zulu", "073 234 5678", "active"),
    ("Sipho Dlamini", "074 345 6789", "active"),
    ("Nomsa Khumalo", "076 456 7890", "active"),
    ("Kagiso Mokwena", "078 567 8901", "active"),
    ("Zanele Nkosi", "079 678 9012", "active"),
    ("Bongani Mokoena", "071 789 0123", "active"),
]

ROUTES = [
    ("Thohoyandou – Sibasa", 12.5),
    ("Makhado – Louis Trichardt", 35.0),
    ("Polokwane – Seshego", 18.0),
]

DEPOTS = [
    ("Sibasa Main Depot", "parking", "65 Main Road, Sibasa, Limpopo"),
    ("Thohoyandou Workshop", "workshop", "12 Hlanganani Street, Thohoyandou"),
]

REMUNERATION_PACKAGES = [
    ("Standard Daily Rate", 35000, "daily"),    # R350/day
    ("Weekly Flat Rate", 150000, "weekly"),     # R1500/week
    ("Monthly Salary", 500000, "monthly"),      # R5000/month
]

INSURANCE_DATA = [
    ("Old Mutual", "OM-TXI-2024-001", 35000),   # R350/mo
    ("Santam", "SAN-TXI-2024-002", 42000),      # R420/mo
    ("Hollard", "HOL-TXI-2024-003", 38000),     # R380/mo
    ("MiWay", "MWY-TXI-2024-004", 28000),       # R280/mo
    ("Old Mutual", "OM-TXI-2024-005", 35000),   # R350/mo
]

LOAN_DATA = [
    ("Nedbank", 35000000, 12000000, 500000, 24),   # R350k loan, R120k remaining, R5k/mo, 24mo term
    ("ABSA", 42000000, 18000000, 600000, 30),        # R420k loan, R180k remaining, R6k/mo, 30mo term
]

SPARE_PARTS = [
    ("Brake pads & discs (front set)", 85000),     # R850
    ("Oil filter & air filter", 45000),            # R450
    ("Clutch kit replacement", 250000),            # R2500
    ("CV joint (left)", 120000),                   # R1200
    ("Wheel bearing set", 95000),                  # R950
]

MECHANICS = [
    ("Stephen Ndlovu", "Clutch replacement labour"),
    ("Joseph Mthembu", "Brake service & wheel alignment"),
    ("Samuel Radebe", "Engine diagnostics & tune-up"),
]

# ── Daily income generation patterns ─────────────────────────────────────

WEEKDAY_PATTERNS = {
    0: (600, 1800),   # Monday
    1: (600, 2000),   # Tuesday
    2: (600, 2000),   # Wednesday
    3: (600, 1800),   # Thursday
    4: (700, 2200),   # Friday
    5: (800, 2500),   # Saturday
    6: (0, 0),        # Sunday (rest day)
}

# Per-taxi modifier (some earn more, some less)
TAXI_INCOME_MODIFIER = [1.0, 1.2, 0.9, 1.1, 1.0, 0.85, 1.05]


def _seed_routes(db: Session, org_id: str) -> list[Route]:
    routes = []
    for name, dist in ROUTES:
        r = Route(organisation_id=org_id, name=name, distance_km=dist)
        db.add(r)
        routes.append(r)
    return routes


def _seed_depots(db: Session, org_id: str) -> list[Depot]:
    depots = []
    for name, d_type, addr in DEPOTS:
        d = Depot(organisation_id=org_id, name=name, depot_type=d_type, address=addr)
        db.add(d)
        depots.append(d)
    return depots


def _seed_taxis(db: Session, org_id: str, routes: list[Route]) -> list[Taxi]:
    taxis = []
    for i, (reg, model, status) in enumerate(TAXIS):
        t = Taxi(
            organisation_id=org_id,
            registration_number=reg,
            model=model,
            status=status,
            assigned_route_id=routes[i % len(routes)].id if i < 5 else None,
        )
        db.add(t)
        taxis.append(t)
    return taxis


def _seed_drivers(db: Session, org_id: str, taxis: list[Taxi]) -> list[Driver]:
    drivers = []
    for i, (name, phone, status) in enumerate(DRIVERS):
        d = Driver(
            organisation_id=org_id,
            name=name,
            phone=phone,
            status=status,
            assigned_taxi_id=taxis[i % len(taxis)].id if i < 5 else None,
        )
        db.add(d)
        drivers.append(d)
    return drivers


def _seed_remuneration(db: Session, org_id: str) -> list[RemunerationPackage]:
    pkgs = []
    for name, salary, freq in REMUNERATION_PACKAGES:
        p = RemunerationPackage(
            organisation_id=org_id,
            name=name,
            base_salary_cents=salary,
            payment_frequency=freq,
        )
        db.add(p)
        pkgs.append(p)
    return pkgs


def _seed_employees(
    db: Session, org_id: str, drivers: list[Driver], pkgs: list[RemunerationPackage], depots: list[Depot]
) -> list[Employee]:
    today = date.today()
    employees = []
    for i, d in enumerate(drivers):
        hire = today - timedelta(days=180 + i * 30)
        emp = Employee(
            organisation_id=org_id,
            driver_id=d.id,
            remuneration_package_id=pkgs[i % len(pkgs)].id,
            depot_id=depots[i % len(depots)].id,
            employment_status="active",
            hire_date=hire,
        )
        db.add(emp)
        employees.append(emp)
    return employees


def _seed_insurance(db: Session, org_id: str, taxis: list[Taxi]) -> list[Insurance]:
    today = date.today()
    policies = []
    for i, (insurer, policy, premium) in enumerate(INSURANCE_DATA):
        pol = Insurance(
            organisation_id=org_id,
            taxi_id=taxis[i].id,
            insurer=insurer,
            policy_number=policy,
            monthly_premium_cents=premium,
            start_date=today - timedelta(days=365),
            end_date=today + timedelta(days=365),
        )
        db.add(pol)
        policies.append(pol)
    return policies


def _seed_loans(db: Session, org_id: str, taxis: list[Taxi]) -> list[TaxiLoan]:
    today = date.today()
    loans = []
    for i, (lender, total, remaining, instalment, term_months) in enumerate(LOAN_DATA):
        ln = TaxiLoan(
            organisation_id=org_id,
            taxi_id=taxis[i].id,
            lender=lender,
            total_amount_cents=total,
            remaining_balance_cents=remaining,
            monthly_instalment_cents=instalment,
            start_date=today - timedelta(days=90),
        )
        db.add(ln)
        loans.append(ln)
    return loans


def _seed_income(
    db: Session,
    org_id: str,
    taxis: list[Taxi],
    drivers: list[Driver],
    routes: list[Route],
    user_id: str,
) -> list[DailyIncome]:
    today = date.today()
    entries = []
    inc_route_map = []

    for day_offset in range(30, 0, -1):
        d = today - timedelta(days=day_offset)
        dow = d.weekday()
        min_earn, max_earn = WEEKDAY_PATTERNS[dow]
        if max_earn == 0:
            continue

        for ti, taxi in enumerate(taxis):
            earn_range = int(min_earn * TAXI_INCOME_MODIFIER[ti])
            max_range = int(max_earn * TAXI_INCOME_MODIFIER[ti])
            amount = random.randint(earn_range, max_range) * 100

            driver = drivers[ti % len(drivers)]
            inc = DailyIncome(
                organisation_id=org_id,
                taxi_id=taxi.id,
                driver_id=driver.id,
                date=d,
                total_cash=amount,
                captured_by=user_id,
                notes="" if random.random() > 0.3 else "Good day",
            )
            db.add(inc)
            entries.append(inc)

            if random.random() < 0.6:
                route = routes[ti % len(routes)]
                inc_route_map.append((inc, route.id))

    db.flush()

    for inc, route_id in inc_route_map:
        ra = RouteAssignment(
            organisation_id=org_id,
            daily_income_id=inc.id,
            route_id=route_id,
        )
        db.add(ra)

    return entries


def _seed_breakdowns(
    db: Session, org_id: str, taxis: list[Taxi], user_id: str
) -> list[Breakdown]:
    today = date.today()
    breakdowns = []

    bd_data = [
        (taxis[2], "Engine overheating — coolant leak", 15, 18),
        (taxis[4], "Brake failure — replaced pads and discs", 2, 10),
        (taxis[1], "Clutch worn out — full replacement", 3, 12),
    ]

    for taxi, reason, days_ago, duration_hours in bd_data:
        start = today - timedelta(days=days_ago, hours=8)
        end = start + timedelta(hours=duration_hours)
        cost = random.randint(50, 300) * 100  # R5000 - R30000
        bd = Breakdown(
            organisation_id=org_id,
            taxi_id=taxi.id,
            start_time=start,
            end_time=end,
            reason=reason,
            cost_total=cost,
            captured_by=user_id,
        )
        db.add(bd)
        breakdowns.append(bd)

    # One open breakdown
    open_bd = Breakdown(
        organisation_id=org_id,
        taxi_id=taxis[5].id,
        start_time=today - timedelta(days=1, hours=4),
        end_time=None,
        reason="Suspected gearbox issue — awaiting mechanic",
        cost_total=None,
        captured_by=user_id,
    )
    db.add(open_bd)
    breakdowns.append(open_bd)

    return breakdowns


def _seed_fuel(
    db: Session, org_id: str, taxis: list[Taxi], user_id: str
) -> list[Fuel]:
    today = date.today()
    entries = []

    for taxi in taxis:
        entries_per_taxi = random.randint(4, 8)
        for _ in range(entries_per_taxi):
            days_ago = random.randint(1, 29)
            litres = round(random.uniform(20, 65), 1)
            cost = int(litres * 23.50) * 100  # R23.50/litre diesel
            fuel = Fuel(
                organisation_id=org_id,
                taxi_id=taxi.id,
                date=today - timedelta(days=days_ago),
                litres=litres,
                cost_total=cost,
                odometer_km=random.randint(5000, 80000),
                captured_by=user_id,
            )
            db.add(fuel)
            entries.append(fuel)

    return entries


def _seed_loan_payments(
    db: Session, org_id: str, loans: list[TaxiLoan], user_id: str
) -> list[LoanPayment]:
    today = date.today()
    payments = []
    for loan in loans:
        for month in range(1, 4):
            pay_date = today.replace(day=15) - timedelta(days=30 * month)
            lp = LoanPayment(
                organisation_id=org_id,
                loan_id=loan.id,
                amount_cents=loan.monthly_instalment_cents,
                payment_date=pay_date,
                reference=f"LOAN-{loan.id[:6].upper()}-{month}",
                created_by=user_id,
            )
            db.add(lp)
            payments.append(lp)
    return payments


def _seed_salary_payments(
    db: Session, org_id: str, employees: list[Employee], user_id: str
) -> list[SalaryPayment]:
    today = date.today()
    payments = []
    for emp in employees:
        for month in range(1, 3):
            pay_date = today.replace(day=25) - timedelta(days=30 * month)
            sp = SalaryPayment(
                organisation_id=org_id,
                employee_id=emp.id,
                amount_cents=random.randint(300000, 800000),
                payment_date=pay_date,
                payment_method="cash",
                reference=f"SAL-{emp.id[:6].upper()}-{month}",
                created_by=user_id,
            )
            db.add(sp)
            payments.append(sp)
    return payments


def _seed_spare_parts(
    db: Session, org_id: str, depots: list[Depot], taxis: list[Taxi], user_id: str
) -> list[SparePartPurchase]:
    today = date.today()
    parts = []
    for i, (desc, cost) in enumerate(SPARE_PARTS):
        sp = SparePartPurchase(
            organisation_id=org_id,
            depot_id=depots[0].id,
            taxi_id=taxis[i % len(taxis)].id,
            description=desc,
            cost_total_cents=cost,
            date=today - timedelta(days=random.randint(5, 60)),
            created_by=user_id,
        )
        db.add(sp)
        parts.append(sp)
    return parts


def _seed_mechanic_payments(
    db: Session, org_id: str, depots: list[Depot], taxis: list[Taxi], user_id: str
) -> list[MechanicPayment]:
    today = date.today()
    payments = []
    for i, (mech, desc) in enumerate(MECHANICS):
        mp = MechanicPayment(
            organisation_id=org_id,
            depot_id=depots[1].id,
            taxi_id=taxis[i * 2 % len(taxis)].id,
            mechanic_name=mech,
            description=desc,
            amount_cents=random.randint(50000, 200000),
            payment_date=today - timedelta(days=random.randint(3, 45)),
            payment_method="cash",
            created_by=user_id,
        )
        db.add(mp)
        payments.append(mp)
    return payments


# ── Public API ────────────────────────────────────────────────────────────


def seed_organisation(db: Session, org_id: str, user_id: str) -> dict:
    """Load realistic demo data for an organisation. Idempotent — if data
    already exists, aborts early."""
    existing = db.query(func.count(Taxi.id)).filter(Taxi.organisation_id == org_id).scalar()
    if existing:
        return {"seeded": False, "reason": "Organisation already has data"}

    routes = _seed_routes(db, org_id)
    depots = _seed_depots(db, org_id)
    db.flush()  # ensure routes/depots have IDs

    taxis = _seed_taxis(db, org_id, routes)
    db.flush()  # ensure taxis have IDs

    drivers = _seed_drivers(db, org_id, taxis)
    pkgs = _seed_remuneration(db, org_id)
    db.flush()  # ensure drivers and packages have IDs

    employees = _seed_employees(db, org_id, drivers, pkgs, depots)
    _seed_insurance(db, org_id, taxis)
    loans = _seed_loans(db, org_id, taxis)
    _seed_income(db, org_id, taxis, drivers, routes, user_id)
    _seed_breakdowns(db, org_id, taxis, user_id)
    _seed_fuel(db, org_id, taxis, user_id)
    _seed_loan_payments(db, org_id, loans, user_id)
    _seed_salary_payments(db, org_id, employees, user_id)
    _seed_spare_parts(db, org_id, depots, taxis, user_id)
    _seed_mechanic_payments(db, org_id, depots, taxis, user_id)

    db.commit()

    taxi_c = db.query(func.count(Taxi.id)).filter(Taxi.organisation_id == org_id).scalar()
    driver_c = db.query(func.count(Driver.id)).filter(Driver.organisation_id == org_id).scalar()
    income_c = db.query(func.count(DailyIncome.id)).filter(DailyIncome.organisation_id == org_id).scalar()
    bd_c = db.query(func.count(Breakdown.id)).filter(Breakdown.organisation_id == org_id).scalar()
    fuel_c = db.query(func.count(Fuel.id)).filter(Fuel.organisation_id == org_id).scalar()

    return {
        "seeded": True,
        "reason": "Demo data loaded successfully",
        "stats": {
            "taxis": taxi_c,
            "drivers": driver_c,
            "income_entries": income_c,
            "breakdowns": bd_c,
            "fuel_entries": fuel_c,
        },
    }


def clear_organisation_data(db: Session, org_id: str) -> dict:
    """Remove all seeded operational data for an organisation.
    Preserves the organisation itself, users, settings, and subscription."""
    tables = [
        MechanicPayment, SparePartPurchase, LoanPayment, SalaryPayment,
        Employee, RemunerationPackage, Fuel, Breakdown, RouteAssignment,
        DailyIncome, Insurance, TaxiLoan, Driver, Taxi, Depot, Route,
        AuditLog, Notification,
    ]

    counts = {}
    for model in tables:
        count = db.query(model).filter(model.organisation_id == org_id).delete()
        counts[model.__tablename__] = count

    db.commit()
    return {"cleared": True, "deleted": counts}


def seed_status(db: Session, org_id: str) -> dict:
    """Check whether the organisation has any data loaded."""
    taxi_count = db.query(func.count(Taxi.id)).filter(Taxi.organisation_id == org_id).scalar()
    income_count = db.query(func.count(DailyIncome.id)).filter(DailyIncome.organisation_id == org_id).scalar()
    driver_count = db.query(func.count(Driver.id)).filter(Driver.organisation_id == org_id).scalar()
    return {
        "has_data": taxi_count > 0 or income_count > 0,
        "counts": {
            "taxis": taxi_count,
            "drivers": driver_count,
            "income_entries": income_count,
        },
    }
