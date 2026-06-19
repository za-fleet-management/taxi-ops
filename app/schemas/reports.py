from datetime import date, datetime

from pydantic import BaseModel


class IncomeSummaryItem(BaseModel):
    date: date
    total_cash: int
    entry_count: int


class IncomeSummaryResponse(BaseModel):
    items: list[IncomeSummaryItem]
    grand_total: int


class DriverPerformanceItem(BaseModel):
    driver_id: str
    driver_name: str
    total_income_cents: int
    income_days: int
    idle_days: int


class DriverPerformanceResponse(BaseModel):
    items: list[DriverPerformanceItem]


class DowntimeCostItem(BaseModel):
    breakdown_id: str
    taxi_id: str
    registration_number: str
    start_time: datetime
    end_time: datetime | None
    duration_hours: float
    cost_total: int | None


class DowntimeCostResponse(BaseModel):
    items: list[DowntimeCostItem]
    total_cost: int


class CostOfOperationsItem(BaseModel):
    taxi_id: str
    registration_number: str
    total_income: int
    total_fuel_cost: int
    total_breakdown_cost: int
    total_insurance_cost: int
    total_loan_payment_cost: int
    total_spare_part_cost: int
    total_mechanic_payment_cost: int
    cost_of_operations: int
    net_position: int


class CostOfOperationsResponse(BaseModel):
    items: list[CostOfOperationsItem]


class RouteProfitabilityItem(BaseModel):
    route_id: str
    route_name: str
    distance_km: float | None
    income_count: int
    total_income: int
    allocated_fuel_cost: int
    allocated_breakdown_cost: int
    allocated_costs: int
    profit: int
    allocation_note: str


class RouteProfitabilityResponse(BaseModel):
    items: list[RouteProfitabilityItem]
