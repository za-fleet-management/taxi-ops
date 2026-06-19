from datetime import date, datetime

from pydantic import BaseModel, Field


class OrganisationSettingsUpdate(BaseModel):
    vat_registered: bool | None = None
    vat_number: str | None = None
    financial_year_end: date | None = None
    default_currency: str | None = Field(None, min_length=3, max_length=3)


class OrganisationProfileUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    region: str | None = Field(None, min_length=1, max_length=255)


class OrganisationSettingsResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    vat_registered: bool
    vat_number: str | None
    financial_year_end: date
    default_currency: str
    created_at: datetime
    updated_at: datetime


class OrganisationProfileResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    region: str
    created_at: datetime


class AdminDashboardResponse(BaseModel):
    active_taxis: int
    total_taxis: int
    active_drivers: int
    total_drivers: int
    income_this_month: int
    open_breakdowns: int
    unconfirmed_payments: int
    bank_unconfirmed_payments: int
    sub_days_remaining: int
    sub_expired: bool
    recent_audit_entries: list[dict]
    notifications: list[dict]


class AuditLogEntry(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    user_id: str
    user_name: str | None = None
    action: str
    entity_type: str
    entity_id: str | None
    details: str | None
    created_at: datetime


class NotificationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    type: str
    title: str
    message: str
    link: str | None
    dismissed: bool
    created_at: datetime
