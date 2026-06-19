from datetime import date, datetime

from pydantic import BaseModel, Field


class SalaryPaymentCreate(BaseModel):
    employee_id: str = Field(..., min_length=1)
    amount_cents: int = Field(..., gt=0)
    payment_date: date
    payment_method: str = Field(default="cash", pattern="^(cash|eft|other)$")
    reference: str | None = Field(None, max_length=255)
    notes: str | None = Field(None, max_length=500)


class SalaryPaymentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    employee_id: str
    amount_cents: int
    payment_date: date
    payment_method: str
    reference: str | None
    notes: str | None
    created_by: str
    created_at: datetime


class SalaryPaymentWithEmployee(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    employee_id: str
    driver_name: str
    amount_cents: int
    payment_date: date
    payment_method: str
    reference: str | None
    notes: str | None
    created_by: str
    created_at: datetime
