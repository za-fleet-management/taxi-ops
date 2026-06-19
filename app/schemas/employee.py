from datetime import date, datetime

from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
    driver_id: str = Field(..., min_length=1)
    remuneration_package_id: str | None = None
    depot_id: str | None = None
    hire_date: date


class EmployeeUpdate(BaseModel):
    remuneration_package_id: str | None = None
    depot_id: str | None = None
    employment_status: str | None = Field(None, pattern="^(active|terminated)$")
    hire_date: date | None = None
    termination_date: date | None = None


class EmployeeResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    driver_id: str
    remuneration_package_id: str | None
    depot_id: str | None
    employment_status: str
    hire_date: date
    termination_date: date | None
    created_at: datetime


class EmployeeWithDetails(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    driver_id: str
    driver_name: str
    driver_phone: str
    remuneration_package_id: str | None
    package_name: str | None
    base_salary_cents: int | None
    payment_frequency: str | None
    depot_id: str | None
    depot_name: str | None
    employment_status: str
    hire_date: date
    termination_date: date | None
    created_at: datetime


class EmployeeBalanceResponse(BaseModel):
    employee_id: str
    driver_name: str
    period_start: date
    period_end: date
    base_salary_cents: int
    payment_frequency: str
    days_employed: int
    days_in_period: int
    owed_cents: int
    paid_cents: int
    balance_cents: int
