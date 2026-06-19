from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_accountant_or_above, require_owner
from app.database import get_db
from app.models.depot import Depot
from app.models.driver import Driver
from app.models.employee import Employee
from app.models.remuneration import RemunerationPackage
from app.models.salary_payment import SalaryPayment
from app.models.user import User
from app.schemas.employee import (
    EmployeeBalanceResponse,
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
    EmployeeWithDetails,
)

router = APIRouter(prefix="/employees", tags=["employees"])


def _employee_details(emp: Employee, db: Session) -> dict:
    driver = db.query(Driver).filter(Driver.id == emp.driver_id).first()
    pkg = None
    if emp.remuneration_package_id:
        pkg = db.query(RemunerationPackage).filter(
            RemunerationPackage.id == emp.remuneration_package_id
        ).first()
    depot = None
    if emp.depot_id:
        depot = db.query(Depot).filter(Depot.id == emp.depot_id).first()
    return {
        "id": emp.id,
        "organisation_id": emp.organisation_id,
        "driver_id": emp.driver_id,
        "driver_name": driver.name if driver else "Unknown",
        "driver_phone": driver.phone if driver else "",
        "remuneration_package_id": emp.remuneration_package_id,
        "package_name": pkg.name if pkg else None,
        "base_salary_cents": pkg.base_salary_cents if pkg else None,
        "payment_frequency": pkg.payment_frequency if pkg else None,
        "depot_id": emp.depot_id,
        "depot_name": depot.name if depot else None,
        "employment_status": emp.employment_status,
        "hire_date": emp.hire_date,
        "termination_date": emp.termination_date,
        "created_at": emp.created_at,
    }


@router.get("", response_model=list[EmployeeWithDetails])
def list_employees(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(require_accountant_or_above),
):
    q = db.query(Employee).filter(Employee.organisation_id == user.organisation_id)
    if status_filter:
        q = q.filter(Employee.employment_status == status_filter)
    employees = q.order_by(Employee.created_at.desc()).all()
    return [_employee_details(e, db) for e in employees]


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(
    body: EmployeeCreate,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    driver = db.query(Driver).filter(
        Driver.id == body.driver_id,
        Driver.organisation_id == user.organisation_id,
    ).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    if body.remuneration_package_id:
        pkg = db.query(RemunerationPackage).filter(
            RemunerationPackage.id == body.remuneration_package_id,
            RemunerationPackage.organisation_id == user.organisation_id,
        ).first()
        if not pkg:
            raise HTTPException(status_code=404, detail="Remuneration package not found")

    if body.depot_id:
        depot = db.query(Depot).filter(
            Depot.id == body.depot_id,
            Depot.organisation_id == user.organisation_id,
        ).first()
        if not depot:
            raise HTTPException(status_code=404, detail="Depot not found")

    existing = db.query(Employee).filter(
        Employee.organisation_id == user.organisation_id,
        Employee.driver_id == body.driver_id,
    ).first()
    if existing:
        # Driver already has an auto-created employment record; update it.
        if body.remuneration_package_id is not None:
            if body.remuneration_package_id:
                pkg = db.query(RemunerationPackage).filter(
                    RemunerationPackage.id == body.remuneration_package_id,
                    RemunerationPackage.organisation_id == user.organisation_id,
                ).first()
                if not pkg:
                    raise HTTPException(status_code=404, detail="Remuneration package not found")
            existing.remuneration_package_id = body.remuneration_package_id or None
        if body.depot_id is not None:
            if body.depot_id:
                depot = db.query(Depot).filter(
                    Depot.id == body.depot_id,
                    Depot.organisation_id == user.organisation_id,
                ).first()
                if not depot:
                    raise HTTPException(status_code=404, detail="Depot not found")
            existing.depot_id = body.depot_id or None
        if body.hire_date is not None:
            existing.hire_date = body.hire_date
        db.commit()
        db.refresh(existing)
        response.status_code = status.HTTP_200_OK
        return existing

    emp = Employee(
        organisation_id=user.organisation_id,
        driver_id=body.driver_id,
        remuneration_package_id=body.remuneration_package_id,
        depot_id=body.depot_id,
        hire_date=body.hire_date,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@router.patch("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: str,
    body: EmployeeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    emp = (
        db.query(Employee)
        .filter(
            Employee.id == employee_id,
            Employee.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if body.remuneration_package_id is not None:
        if body.remuneration_package_id:
            pkg = db.query(RemunerationPackage).filter(
                RemunerationPackage.id == body.remuneration_package_id,
                RemunerationPackage.organisation_id == user.organisation_id,
            ).first()
            if not pkg:
                raise HTTPException(status_code=404, detail="Remuneration package not found")
        emp.remuneration_package_id = body.remuneration_package_id or None
    if body.depot_id is not None:
        if body.depot_id:
            depot = db.query(Depot).filter(
                Depot.id == body.depot_id,
                Depot.organisation_id == user.organisation_id,
            ).first()
            if not depot:
                raise HTTPException(status_code=404, detail="Depot not found")
        emp.depot_id = body.depot_id or None
    if body.employment_status is not None:
        emp.employment_status = body.employment_status
    if body.hire_date is not None:
        emp.hire_date = body.hire_date
    if body.termination_date is not None:
        emp.termination_date = body.termination_date
    db.commit()
    db.refresh(emp)
    return emp


@router.get("/{employee_id}/balance", response_model=EmployeeBalanceResponse)
def employee_balance(
    employee_id: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_accountant_or_above),
):
    emp = (
        db.query(Employee)
        .filter(
            Employee.id == employee_id,
            Employee.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    driver = db.query(Driver).filter(Driver.id == emp.driver_id).first()
    pkg = None
    if emp.remuneration_package_id:
        pkg = db.query(RemunerationPackage).filter(
            RemunerationPackage.id == emp.remuneration_package_id
        ).first()

    base_salary = pkg.base_salary_cents if pkg else 0
    payment_frequency = pkg.payment_frequency if pkg else "monthly"

    hire = max(emp.hire_date, start_date)
    term = emp.termination_date or end_date
    term = min(term, end_date)
    days_employed = max(0, (term - hire).days + 1)
    days_in_period = max(1, (end_date - start_date).days + 1)

    if payment_frequency == "weekly":
        owed = int(base_salary * days_employed / 7)
    else:
        owed = int(base_salary * days_employed / days_in_period)

    paid = (
        db.query(func.coalesce(func.sum(SalaryPayment.amount_cents), 0))
        .filter(
            SalaryPayment.organisation_id == user.organisation_id,
            SalaryPayment.employee_id == employee_id,
            SalaryPayment.payment_date >= start_date,
            SalaryPayment.payment_date <= end_date,
        )
        .scalar()
    )

    return EmployeeBalanceResponse(
        employee_id=emp.id,
        driver_name=driver.name if driver else "Unknown",
        period_start=start_date,
        period_end=end_date,
        base_salary_cents=base_salary,
        payment_frequency=payment_frequency,
        days_employed=days_employed,
        days_in_period=days_in_period,
        owed_cents=owed,
        paid_cents=paid,
        balance_cents=owed - paid,
    )
