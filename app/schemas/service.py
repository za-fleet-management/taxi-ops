from datetime import date, datetime

from pydantic import BaseModel, Field


# ── ServiceType ──────────────────────────────────────────────────────────────

class ServiceTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    interval_km: int | None = Field(None, ge=0)
    interval_days: int | None = Field(None, ge=0)
    reminder_days_before: int = Field(default=7, ge=0)


class ServiceTypeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    interval_km: int | None = Field(None, ge=0)
    interval_days: int | None = Field(None, ge=0)
    reminder_days_before: int | None = Field(None, ge=0)
    is_active: bool | None = None


class ServiceTypeResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    name: str
    description: str | None
    interval_km: int | None
    interval_days: int | None
    reminder_days_before: int
    is_active: bool
    created_at: datetime


# ── TaxiServiceSchedule ──────────────────────────────────────────────────────

class TaxiServiceScheduleCreate(BaseModel):
    taxi_id: str = Field(..., min_length=1)
    service_type_id: str = Field(..., min_length=1)
    last_service_date: date | None = None
    last_service_km: int | None = Field(None, ge=0)
    next_due_date: date | None = None
    next_due_km: int | None = Field(None, ge=0)


class TaxiServiceScheduleUpdate(BaseModel):
    last_service_date: date | None = None
    last_service_km: int | None = Field(None, ge=0)
    next_due_date: date | None = None
    next_due_km: int | None = Field(None, ge=0)


class TaxiServiceScheduleResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    taxi_id: str
    service_type_id: str
    last_service_date: date | None
    last_service_km: int | None
    next_due_date: date | None
    next_due_km: int | None
    created_at: datetime


class TaxiServiceScheduleWithNames(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    taxi_id: str
    registration_number: str
    service_type_id: str
    service_type_name: str
    last_service_date: date | None
    last_service_km: int | None
    next_due_date: date | None
    next_due_km: int | None
    created_at: datetime


# ── ServiceRecord ────────────────────────────────────────────────────────────

class ServiceRecordCreate(BaseModel):
    taxi_id: str = Field(..., min_length=1)
    service_type_id: str = Field(..., min_length=1)
    schedule_id: str | None = None
    service_date: date
    odometer_km: int | None = Field(None, ge=0)
    cost_cents: int = Field(..., ge=0)
    vendor: str | None = Field(None, max_length=255)
    notes: str | None = None


class ServiceRecordUpdate(BaseModel):
    service_date: date | None = None
    odometer_km: int | None = Field(None, ge=0)
    cost_cents: int | None = Field(None, ge=0)
    vendor: str | None = Field(None, max_length=255)
    notes: str | None = None


class ServiceRecordResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    taxi_id: str
    service_type_id: str
    schedule_id: str | None
    service_date: date
    odometer_km: int | None
    cost_cents: int
    vendor: str | None
    notes: str | None
    captured_by: str
    created_at: datetime


class ServiceRecordWithNames(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    taxi_id: str
    registration_number: str
    service_type_id: str
    service_type_name: str
    schedule_id: str | None
    service_date: date
    odometer_km: int | None
    cost_cents: int
    vendor: str | None
    notes: str | None
    captured_by: str
    created_at: datetime
