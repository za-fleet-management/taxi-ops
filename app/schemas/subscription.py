from datetime import date, datetime

from pydantic import BaseModel, Field


PLAN_PRICES = {
    1: 15_000,
    3: 15_000,
    6: 12_500,
    12: 10_000,
}


def price_per_taxi_cents(plan_months: int) -> int:
    return PLAN_PRICES.get(plan_months, 15_000)


class PlanQuoteRequest(BaseModel):
    plan_months: int = Field(..., ge=1, le=12)


class PlanQuoteResponse(BaseModel):
    plan_months: int
    price_per_taxi_cents: int
    taxi_count: int
    total_cents: int
    total_display: str  # e.g. "R 3 750"


class PaymentCreate(BaseModel):
    plan_months: int = Field(..., ge=1, le=12)
    amount_cents: int = Field(..., ge=0)
    reference: str = Field(..., min_length=1, max_length=255)
    payment_date: date


class PaymentConfirm(BaseModel):
    notes: str | None = None


class PaymentBankConfirm(BaseModel):
    notes: str | None = None


class PaymentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    subscription_id: str
    amount_cents: int
    reference: str
    payment_date: date
    bank_confirmed: bool
    bank_confirmed_by: str | None
    bank_confirmed_at: datetime | None
    confirmed: bool
    confirmed_by: str | None
    confirmed_at: datetime | None
    notes: str | None
    created_at: datetime


class SubscriptionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    plan_months: int
    price_per_taxi_cents: int
    taxi_count: int
    total_amount_cents: int
    period_start: date
    period_end: date
    status: str
    created_at: datetime
    updated_at: datetime
