from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class Period(BaseModel):
    start_date: date
    end_date: date


class TrendPoint(BaseModel):
    month: str
    revenue_cents: int
    cost_cents: int
    profit_cents: int


class ExecutiveSummaryResponse(BaseModel):
    period: Period
    revenue_cents: int
    total_cost_cents: int
    gross_profit_cents: int
    gross_margin_percent: float
    active_taxis: int
    total_taxis: int
    active_drivers: int
    open_breakdowns: int
    loan_exposure_cents: int
    average_revenue_per_taxi_cents: int
    average_cost_per_taxi_cents: int
    trend: list[TrendPoint]


class IncomeStatementResponse(BaseModel):
    period: Period
    revenue_cents: int
    fuel_cents: int
    breakdown_cents: int
    insurance_cents: int
    loan_payment_cents: int
    spare_part_cents: int
    mechanic_payment_cents: int
    salary_cents: int
    cost_of_operations_cents: int
    gross_profit_cents: int
    gross_margin_percent: float
    operating_expenses_cents: int
    net_profit_cents: int


class CashFlowResponse(BaseModel):
    period: Period
    cash_in_cents: int
    fuel_cents: int
    breakdown_cents: int
    insurance_cents: int
    loan_payment_cents: int
    spare_part_cents: int
    mechanic_payment_cents: int
    salary_cents: int
    total_cash_out_cents: int
    net_cash_movement_cents: int


class BalanceSheetResponse(BaseModel):
    as_at: date
    taxi_assets_cents: int
    spare_parts_inventory_cents: int
    cash_balance_cents: int
    total_assets_cents: int
    loan_outstanding_cents: int
    total_liabilities_cents: int
    equity_cents: int


class TaxiProfitabilityItem(BaseModel):
    taxi_id: str
    registration_number: str
    route_name: str | None
    days_active: int
    total_income_cents: int
    fuel_cents: int
    breakdown_cents: int
    insurance_cents: int
    loan_payment_cents: int
    spare_part_cents: int
    mechanic_payment_cents: int
    driver_salary_owed_cents: int
    total_cost_cents: int
    net_profit_cents: int
    profit_margin_percent: float
    cost_per_active_day_cents: int


class TaxiProfitabilityResponse(BaseModel):
    period: Period
    items: list[TaxiProfitabilityItem]
    summary: dict


class DriverPerformanceItem(BaseModel):
    driver_id: str
    driver_name: str
    taxi_registration: str | None
    income_days: int
    idle_days: int
    total_income_cents: int
    package_name: str | None
    payment_frequency: str | None
    salary_owed_cents: int
    salary_paid_cents: int
    salary_balance_cents: int
    income_per_active_day_cents: int


class DriverPerformanceResponse(BaseModel):
    period: Period
    items: list[DriverPerformanceItem]
    summary: dict


class RouteProfitabilityItem(BaseModel):
    route_id: str
    route_name: str
    distance_km: float | None
    income_count: int
    total_income_cents: int
    allocated_fuel_cents: int
    allocated_breakdown_cents: int
    allocated_salary_cents: int
    allocated_insurance_cents: int
    allocated_loan_cents: int
    total_allocated_cost_cents: int
    profit_cents: int
    profit_per_km_cents: int | None
    profit_per_trip_cents: int | None


class RouteProfitabilityResponse(BaseModel):
    period: Period
    items: list[RouteProfitabilityItem]


class DepotCostItem(BaseModel):
    depot_id: str
    depot_name: str
    depot_type: str
    employees_assigned: int
    spare_parts_cents: int
    mechanic_payments_cents: int
    internal_labour_cents: int
    taxis_serviced: int
    total_cost_cents: int
    cost_per_taxi_cents: int | None
    cost_per_employee_cents: int | None


class DepotCostResponse(BaseModel):
    period: Period
    items: list[DepotCostItem]


class MaintenanceDowntimeItem(BaseModel):
    breakdown_id: str
    taxi_id: str
    registration_number: str
    reason: str | None
    start_time: datetime
    end_time: datetime | None
    duration_hours: float
    cost_total_cents: int | None
    downtime_days: int
    lost_revenue_estimate_cents: int


class MaintenanceDowntimeResponse(BaseModel):
    period: Period
    items: list[MaintenanceDowntimeItem]
    total_cost_cents: int
    total_lost_revenue_cents: int


# ── Phase C — Financial Deep-Dive ──────────────────────────────────────────


class FixedVsVariableItem(BaseModel):
    category: str
    cost_type: str
    amount_cents: int
    percentage: float


class FixedVsVariableResponse(BaseModel):
    period: Period
    items: list[FixedVsVariableItem]
    total_fixed_cents: int
    total_variable_cents: int
    fixed_percentage: float
    variable_percentage: float


class PeriodRevenuePoint(BaseModel):
    label: str
    revenue_cents: int
    previous_revenue_cents: int | None = None


class RevenueByPeriodResponse(BaseModel):
    period: Period
    group_by: str
    series: list[PeriodRevenuePoint]
    total_current_cents: int
    total_previous_cents: int | None
    change_cents: int | None
    change_percent: float | None


class PayrollItem(BaseModel):
    employee_id: str
    driver_name: str
    package_name: str | None
    payment_frequency: str | None
    days_employed: int
    salary_owed_cents: int
    salary_paid_cents: int
    salary_balance_cents: int
    employment_status: str


class PayrollReconciliationResponse(BaseModel):
    period: Period
    items: list[PayrollItem]
    total_owed_cents: int
    total_paid_cents: int
    total_liability_cents: int


class AssetRegisterItem(BaseModel):
    taxi_id: str
    registration_number: str
    model: str | None
    status: str
    purchase_price_cents: int | None
    remaining_balance_cents: int | None
    monthly_instalment_cents: int | None
    insurance_premium_cents: int | None
    total_cost_to_date_cents: int
    total_income_to_date_cents: int
    net_position_cents: int


class AssetRegisterResponse(BaseModel):
    items: list[AssetRegisterItem]
    total_asset_value_cents: int
    total_loan_balance_cents: int
    total_net_position_cents: int


class LoanScheduleItem(BaseModel):
    loan_id: str
    taxi_registration: str
    total_amount_cents: int
    remaining_balance_cents: int
    monthly_instalment_cents: int
    payments_made: int
    total_paid_to_date_cents: int
    remaining_payments: int
    projected_pay_off_date: date | None


class LoanScheduleResponse(BaseModel):
    items: list[LoanScheduleItem]
    total_outstanding_cents: int
    total_original_cents: int
    total_paid_cents: int
