from datetime import date, datetime

from pydantic import BaseModel, Field


class TaxiLoanCreate(BaseModel):
    taxi_id: str = Field(..., min_length=1)
    lender: str = Field(..., min_length=1, max_length=255)
    total_amount_cents: int = Field(..., ge=0)
    remaining_balance_cents: int = Field(..., ge=0)
    monthly_instalment_cents: int = Field(..., ge=0)
    start_date: date
    end_date: date | None = None


class TaxiLoanUpdate(BaseModel):
    lender: str | None = Field(None, min_length=1, max_length=255)
    remaining_balance_cents: int | None = Field(None, ge=0)
    monthly_instalment_cents: int | None = Field(None, ge=0)
    end_date: date | None = None


class TaxiLoanResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    taxi_id: str
    lender: str
    total_amount_cents: int
    remaining_balance_cents: int
    monthly_instalment_cents: int
    start_date: date
    end_date: date | None
    created_at: datetime


class LoanPaymentCreate(BaseModel):
    amount_cents: int = Field(..., gt=0)
    payment_date: date
    reference: str | None = Field(None, max_length=255)


class LoanPaymentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    loan_id: str
    amount_cents: int
    payment_date: date
    reference: str | None
    created_by: str
    created_at: datetime
