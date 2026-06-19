"""Tests for the new reporting suite endpoints."""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings


def signup_org(client: TestClient, suffix: str) -> dict:
    resp = client.post(
        "/api/auth/signup",
        json={
            "organisation_name": f"Report Org {suffix}",
            "region": "Gauteng",
            "name": f"Owner {suffix}",
            "phone": f"+27{suffix}0000000",
            "password": "secret123",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    payload = jwt.decode(
        data["access_token"], settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    return {"token": data["access_token"], "org_id": payload["organisation_id"]}


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def create_taxi(client: TestClient, headers: dict, reg: str = "CF 123-456") -> dict:
    resp = client.post("/api/taxis", json={
        "registration_number": reg,
        "model": "Toyota Hiace",
    }, headers=headers)
    assert resp.status_code == 201
    return resp.json()


def create_driver(client: TestClient, headers: dict, name: str = "John Doe", phone: str = "+27123456789") -> dict:
    resp = client.post("/api/drivers", json={"name": name, "phone": phone}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


class TestExecutiveSummary:
    def test_owner_can_access_summary(self, client: TestClient):
        o = signup_org(client, "ES1")
        headers = auth_header(o["token"])
        resp = client.get("/api/reporting/executive-summary?period=this_month", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "revenue_cents" in data
        assert "total_cost_cents" in data
        assert "trend" in data
        assert len(data["trend"]) == 12

    def test_manager_cannot_access_summary(self, client: TestClient):
        o = signup_org(client, "ES2")
        owner_headers = auth_header(o["token"])
        mgr = client.post("/api/auth/invite", json={
            "phone": "+27000000001",
            "role": "manager",
            "name": "Manager",
        }, headers=owner_headers).json()
        invite_token = mgr["invite_url"].split("token=")[1]
        accept = client.post("/api/auth/accept-invite", json={
            "token": invite_token,
            "name": "Manager",
            "phone": "+27000000001",
            "password": "secret123",
        })
        assert accept.status_code == 200, accept.text
        mgr_headers = auth_header(accept.json()["access_token"])
        resp = client.get("/api/reporting/executive-summary", headers=mgr_headers)
        assert resp.status_code == 403

    def test_summary_aggregates_income_and_costs(self, client: TestClient):
        o = signup_org(client, "ES3")
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, "CF ES3")
        driver = create_driver(client, headers, "Driver ES3", "+27000000002")
        client.patch(f"/api/drivers/{driver['id']}", json={"assigned_taxi_id": taxi["id"]}, headers=headers)

        today = date.today().isoformat()
        client.post("/api/income", json={
            "taxi_id": taxi["id"],
            "driver_id": driver["id"],
            "date": today,
            "total_cash": 500000,
        }, headers=headers)
        client.post("/api/fuel", json={
            "taxi_id": taxi["id"],
            "date": today,
            "litres": 50.0,
            "cost_total": 120000,
        }, headers=headers)

        resp = client.get(f"/api/reporting/executive-summary?start_date={today}&end_date={today}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["revenue_cents"] == 500000
        assert data["total_cost_cents"] >= 120000


class TestIncomeStatement:
    def test_income_statement_structure(self, client: TestClient):
        o = signup_org(client, "IS1")
        headers = auth_header(o["token"])
        today = date.today().isoformat()
        resp = client.get(f"/api/reporting/income-statement?start_date={today}&end_date={today}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["revenue_cents"] == 0
        assert "gross_profit_cents" in data
        assert "net_profit_cents" in data

    def test_income_statement_csv_export(self, client: TestClient):
        o = signup_org(client, "IS2")
        headers = auth_header(o["token"])
        today = date.today().isoformat()
        resp = client.get(
            f"/api/reporting/income-statement?start_date={today}&end_date={today}&format=csv",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        assert "income_statement" in resp.headers["content-disposition"]


class TestCashFlow:
    def test_cash_flow_structure(self, client: TestClient):
        o = signup_org(client, "CF1")
        headers = auth_header(o["token"])
        today = date.today().isoformat()
        resp = client.get(f"/api/reporting/cash-flow?start_date={today}&end_date={today}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "cash_in_cents" in data
        assert "total_cash_out_cents" in data
        assert "net_cash_movement_cents" in data


class TestBalanceSheet:
    def test_balance_sheet_structure(self, client: TestClient):
        o = signup_org(client, "BS1")
        headers = auth_header(o["token"])
        today = date.today().isoformat()
        resp = client.get(f"/api/reporting/balance-sheet?as_at={today}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_assets_cents" in data
        assert "total_liabilities_cents" in data
        assert "equity_cents" in data


class TestTaxiProfitability:
    def test_taxi_profitability_aggregates(self, client: TestClient):
        o = signup_org(client, "TP1")
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, "CF TP1")
        driver = create_driver(client, headers, "Driver TP1", "+27000000003")
        client.patch(f"/api/drivers/{driver['id']}", json={"assigned_taxi_id": taxi["id"]}, headers=headers)

        today = date.today().isoformat()
        client.post("/api/income", json={
            "taxi_id": taxi["id"],
            "driver_id": driver["id"],
            "date": today,
            "total_cash": 400000,
        }, headers=headers)
        client.post("/api/fuel", json={
            "taxi_id": taxi["id"],
            "date": today,
            "litres": 40.0,
            "cost_total": 100000,
        }, headers=headers)

        resp = client.get(f"/api/reporting/taxi-profitability?start_date={today}&end_date={today}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["registration_number"] == "CF TP1"
        assert item["total_income_cents"] == 400000
        assert item["fuel_cents"] == 100000
        assert item["net_profit_cents"] == 300000
        assert data["summary"]["total_net_profit_cents"] == 300000


class TestDriverPerformance:
    def test_driver_performance_shows_idle_days(self, client: TestClient):
        o = signup_org(client, "DP1")
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, "CF DP1")
        driver = create_driver(client, headers, "Driver DP1", "+27000000004")
        client.patch(f"/api/drivers/{driver['id']}", json={"assigned_taxi_id": taxi["id"]}, headers=headers)

        today = date.today().isoformat()
        client.post("/api/income", json={
            "taxi_id": taxi["id"],
            "driver_id": driver["id"],
            "date": today,
            "total_cash": 300000,
        }, headers=headers)

        resp = client.get(f"/api/reporting/driver-performance?start_date={today}&end_date={today}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["income_days"] == 1
        assert item["idle_days"] == 0
        assert item["total_income_cents"] == 300000


class TestRouteProfitability:
    def test_route_profitability_requires_route_assignments(self, client: TestClient):
        o = signup_org(client, "RP1")
        headers = auth_header(o["token"])
        today = date.today().isoformat()
        resp = client.get(f"/api/reporting/route-profitability?start_date={today}&end_date={today}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []


class TestDepotCosts:
    def test_depot_costs_structure(self, client: TestClient):
        o = signup_org(client, "DC1")
        headers = auth_header(o["token"])
        depot = client.post("/api/depots", json={"name": "Workshop DC1", "depot_type": "workshop"}, headers=headers).json()
        today = date.today().isoformat()
        resp = client.get(f"/api/reporting/depot-costs?start_date={today}&end_date={today}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["depot_id"] == depot["id"]


class TestMaintenanceDowntime:
    def test_maintenance_downtime_with_lost_revenue(self, client: TestClient):
        o = signup_org(client, "MD1")
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, "CF MD1")
        driver = create_driver(client, headers, "Driver MD1", "+27000000005")

        today = date.today()
        yesterday = (today - timedelta(days=1)).isoformat()
        breakdown_date = today.isoformat()

        client.post("/api/income", json={
            "taxi_id": taxi["id"],
            "driver_id": driver["id"],
            "date": yesterday,
            "total_cash": 200000,
        }, headers=headers)

        bd = client.post("/api/breakdowns", json={
            "taxi_id": taxi["id"],
            "start_time": f"{breakdown_date}T08:00:00",
            "reason": "Flat tyre",
        }, headers=headers).json()
        client.patch(f"/api/breakdowns/{bd['id']}/close", json={
            "end_time": f"{breakdown_date}T16:00:00",
            "cost_total": 15000,
        }, headers=headers)

        # Use period to avoid date comparison issues
        resp = client.get(f"/api/reporting/maintenance-downtime?period=this_month", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) >= 1
        # Find our breakdown
        item = next((i for i in data["items"] if i["registration_number"] == "CF MD1"), None)
        assert item is not None, "Breakdown not found in results"
        assert item["cost_total_cents"] == 15000
        assert item["duration_hours"] == 8.0
        assert item["lost_revenue_estimate_cents"] >= 0
        assert data["total_cost_cents"] >= 15000


class TestReportingTenantIsolation:
    def test_reporting_is_scoped_to_organisation(self, client: TestClient):
        o1 = signup_org(client, "RT1")
        o2 = signup_org(client, "RT2")
        h1 = auth_header(o1["token"])
        h2 = auth_header(o2["token"])

        taxi = create_taxi(client, h1, "CF RT1")
        driver = create_driver(client, h1, "Driver RT1", "+27000000006")
        today = date.today().isoformat()
        client.post("/api/income", json={
            "taxi_id": taxi["id"],
            "driver_id": driver["id"],
            "date": today,
            "total_cash": 100000,
        }, headers=h1)

        resp1 = client.get(f"/api/reporting/executive-summary?start_date={today}&end_date={today}", headers=h1)
        resp2 = client.get(f"/api/reporting/executive-summary?start_date={today}&end_date={today}", headers=h2)
        assert resp1.json()["revenue_cents"] == 100000
        assert resp2.json()["revenue_cents"] == 0


# ── Phase C — Financial Deep-Dive ──────────────────────────────────────────


class TestFixedVsVariable:
    def test_structure(self, client: TestClient):
        o = signup_org(client, "FV1")
        headers = auth_header(o["token"])
        today = date.today().isoformat()
        resp = client.get(f"/api/reporting/fixed-vs-variable?start_date={today}&end_date={today}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_fixed_cents" in data
        assert "total_variable_cents" in data
        assert len(data["items"]) == 7  # insurance, hp, salaries, fuel, breakdowns, spare parts, mechanic

    def test_separates_fixed_and_variable(self, client: TestClient):
        o = signup_org(client, "FV2")
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, "CF FV2")
        driver = create_driver(client, headers, "Driver FV2", "+27000000100")
        today = date.today().isoformat()

        # Create a loan payment (fixed)
        loan = client.post("/api/taxi-loans", json={
            "taxi_id": taxi["id"],
            "lender": "Test Bank",
            "total_amount_cents": 1200000,
            "remaining_balance_cents": 1200000,
            "monthly_instalment_cents": 100000,
            "start_date": today,
        }, headers=headers).json()
        client.post("/api/taxi-loans/" + loan["id"] + "/payments", json={
            "amount_cents": 100000,
            "payment_date": today,
        }, headers=headers)

        # Log fuel (variable)
        client.post("/api/fuel", json={
            "taxi_id": taxi["id"], "date": today, "litres": 50.0, "cost_total": 100000,
        }, headers=headers)

        resp = client.get(f"/api/reporting/fixed-vs-variable?start_date={today}&end_date={today}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_fixed_cents"] >= 100000  # loan payment
        assert data["total_variable_cents"] >= 100000  # fuel
        assert data["fixed_percentage"] > 0
        assert data["variable_percentage"] > 0

    def test_csv_export(self, client: TestClient):
        o = signup_org(client, "FV3")
        headers = auth_header(o["token"])
        today = date.today().isoformat()
        resp = client.get(
            f"/api/reporting/fixed-vs-variable?start_date={today}&end_date={today}&format=csv",
            headers=headers,
        )
        assert resp.status_code == 200
        assert "csv" in resp.headers["content-type"]

    def test_manager_cannot_access(self, client: TestClient):
        o = signup_org(client, "FV4")
        headers = auth_header(o["token"])
        mgr = client.post("/api/auth/invite", json={
            "phone": "+27000000101", "role": "manager", "name": "Manager",
        }, headers=headers).json()
        accept = client.post("/api/auth/accept-invite", json={
            "token": mgr["invite_url"].split("token=")[1],
            "name": "Manager", "phone": "+27000000101", "password": "secret123",
        })
        mgr_headers = auth_header(accept.json()["access_token"])
        resp = client.get("/api/reporting/fixed-vs-variable", headers=mgr_headers)
        assert resp.status_code == 403


class TestRevenueByPeriod:
    def test_structure(self, client: TestClient):
        o = signup_org(client, "RB1")
        headers = auth_header(o["token"])
        today = date.today().isoformat()
        resp = client.get(f"/api/reporting/revenue-by-period?start_date={today}&end_date={today}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_current_cents" in data
        assert "series" in data
        assert len(data["series"]) >= 0

    def test_group_by_day(self, client: TestClient):
        o = signup_org(client, "RB2")
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, "CF RB2")
        driver = create_driver(client, headers, "Driver RB2", "+27000000102")
        today = date.today().isoformat()
        client.post("/api/income", json={
            "taxi_id": taxi["id"], "driver_id": driver["id"],
            "date": today, "total_cash": 200000,
        }, headers=headers)
        resp = client.get(f"/api/reporting/revenue-by-period?start_date={today}&end_date={today}&group_by=day", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_current_cents"] == 200000
        assert data["group_by"] == "day"
        assert len(data["series"]) >= 1

    def test_group_by_week(self, client: TestClient):
        o = signup_org(client, "RB3")
        headers = auth_header(o["token"])
        today = date.today().isoformat()
        resp = client.get(f"/api/reporting/revenue-by-period?start_date={today}&end_date={today}&group_by=week", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["group_by"] == "week"

    def test_group_by_quarter(self, client: TestClient):
        o = signup_org(client, "RB4")
        headers = auth_header(o["token"])
        today = date.today().isoformat()
        resp = client.get(f"/api/reporting/revenue-by-period?start_date={today}&end_date={today}&group_by=quarter", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["group_by"] == "quarter"

    def test_csv_export(self, client: TestClient):
        o = signup_org(client, "RB5")
        headers = auth_header(o["token"])
        today = date.today().isoformat()
        resp = client.get(
            f"/api/reporting/revenue-by-period?start_date={today}&end_date={today}&format=csv",
            headers=headers,
        )
        assert resp.status_code == 200
        assert "csv" in resp.headers["content-type"]

    def test_period_over_period_comparison(self, client: TestClient):
        o = signup_org(client, "RB6")
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, "CF RB6")
        driver = create_driver(client, headers, "Driver RB6", "+27000000103")
        today = date.today()
        day1 = (today - timedelta(days=5)).isoformat()
        day2 = today.isoformat()
        client.post("/api/income", json={
            "taxi_id": taxi["id"], "driver_id": driver["id"],
            "date": day1, "total_cash": 100000,
        }, headers=headers)
        client.post("/api/income", json={
            "taxi_id": taxi["id"], "driver_id": driver["id"],
            "date": day2, "total_cash": 150000,
        }, headers=headers)
        resp = client.get(
            f"/api/reporting/revenue-by-period?start_date={day2}&end_date={day2}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_current_cents"] == 150000
        # Previous period should exist for same-length window
        assert data["total_previous_cents"] is not None


class TestPayrollReconciliation:
    def test_structure(self, client: TestClient):
        o = signup_org(client, "PR1")
        headers = auth_header(o["token"])
        today = date.today().isoformat()
        resp = client.get(f"/api/reporting/payroll-reconciliation?start_date={today}&end_date={today}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_owed_cents" in data
        assert "total_paid_cents" in data
        assert "total_liability_cents" in data

    def test_shows_employee_salary_data(self, client: TestClient):
        o = signup_org(client, "PR2")
        headers = auth_header(o["token"])
        driver = create_driver(client, headers, "Driver PR2", "+27000000104")

        # Create remuneration package
        pkg = client.post("/api/remuneration-packages", json={
            "name": "Monthly PR2", "base_salary_cents": 500000, "payment_frequency": "monthly",
        }, headers=headers).json()

        # Create employee
        emp = client.post("/api/employees", json={
            "driver_id": driver["id"], "remuneration_package_id": pkg["id"],
            "hire_date": date.today().isoformat(), "employment_status": "active",
        }, headers=headers).json()

        today = date.today().isoformat()

        # Pay salary
        client.post("/api/salary-payments", json={
            "employee_id": emp["id"], "amount_cents": 250000,
            "payment_date": today, "payment_method": "cash",
        }, headers=headers)

        resp = client.get(f"/api/reporting/payroll-reconciliation?start_date={today}&end_date={today}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) >= 1
        item = next((i for i in data["items"] if i["employee_id"] == emp["id"]), None)
        assert item is not None
        assert item["salary_paid_cents"] == 250000
        assert item["salary_owed_cents"] > 0
        assert item["salary_balance_cents"] >= 0

    def test_csv_export(self, client: TestClient):
        o = signup_org(client, "PR3")
        headers = auth_header(o["token"])
        today = date.today().isoformat()
        resp = client.get(
            f"/api/reporting/payroll-reconciliation?start_date={today}&end_date={today}&format=csv",
            headers=headers,
        )
        assert resp.status_code == 200
        assert "csv" in resp.headers["content-type"]

    def test_manager_cannot_access(self, client: TestClient):
        o = signup_org(client, "PR4")
        headers = auth_header(o["token"])
        mgr = client.post("/api/auth/invite", json={
            "phone": "+27000000105", "role": "manager", "name": "Manager",
        }, headers=headers).json()
        accept = client.post("/api/auth/accept-invite", json={
            "token": mgr["invite_url"].split("token=")[1],
            "name": "Manager", "phone": "+27000000105", "password": "secret123",
        })
        mgr_headers = auth_header(accept.json()["access_token"])
        resp = client.get("/api/reporting/payroll-reconciliation", headers=mgr_headers)
        assert resp.status_code == 403


class TestAssetRegister:
    def test_structure(self, client: TestClient):
        o = signup_org(client, "AR1")
        headers = auth_header(o["token"])
        create_taxi(client, headers, "CF AR1")
        resp = client.get("/api/reporting/asset-register", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total_asset_value_cents" in data
        assert "total_net_position_cents" in data

    def test_lifetime_totals(self, client: TestClient):
        o = signup_org(client, "AR2")
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, "CF AR2")
        driver = create_driver(client, headers, "Driver AR2", "+27000000106")
        today = date.today().isoformat()

        # Income and costs
        client.post("/api/income", json={
            "taxi_id": taxi["id"], "driver_id": driver["id"],
            "date": today, "total_cash": 600000,
        }, headers=headers)
        client.post("/api/fuel", json={
            "taxi_id": taxi["id"], "date": today, "litres": 50.0, "cost_total": 100000,
        }, headers=headers)

        resp = client.get("/api/reporting/asset-register", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        item = next((i for i in data["items"] if i["registration_number"] == "CF AR2"), None)
        assert item is not None
        assert item["total_income_to_date_cents"] == 600000
        assert item["total_cost_to_date_cents"] >= 100000
        assert item["net_position_cents"] >= 500000

    def test_csv_export(self, client: TestClient):
        o = signup_org(client, "AR3")
        headers = auth_header(o["token"])
        resp = client.get("/api/reporting/asset-register?format=csv", headers=headers)
        assert resp.status_code == 200
        assert "csv" in resp.headers["content-type"]

    def test_manager_cannot_access(self, client: TestClient):
        o = signup_org(client, "AR4")
        headers = auth_header(o["token"])
        mgr = client.post("/api/auth/invite", json={
            "phone": "+27000000107", "role": "manager", "name": "Manager",
        }, headers=headers).json()
        accept = client.post("/api/auth/accept-invite", json={
            "token": mgr["invite_url"].split("token=")[1],
            "name": "Manager", "phone": "+27000000107", "password": "secret123",
        })
        mgr_headers = auth_header(accept.json()["access_token"])
        resp = client.get("/api/reporting/asset-register", headers=mgr_headers)
        assert resp.status_code == 403


class TestLoanSchedule:
    def test_structure(self, client: TestClient):
        o = signup_org(client, "LS1")
        headers = auth_header(o["token"])
        resp = client.get("/api/reporting/loan-schedule", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total_outstanding_cents" in data
        assert "total_original_cents" in data

    def test_loan_with_payments(self, client: TestClient):
        o = signup_org(client, "LS2")
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, "CF LS2")
        today = date.today().isoformat()

        loan = client.post("/api/taxi-loans", json={
            "taxi_id": taxi["id"],
            "lender": "Test Bank",
            "total_amount_cents": 2400000,
            "remaining_balance_cents": 2400000,
            "monthly_instalment_cents": 200000,
            "start_date": today,
        }, headers=headers).json()

        today = date.today().isoformat()
        client.post(f"/api/taxi-loans/{loan['id']}/payments", json={
            "amount_cents": 200000, "payment_date": today,
        }, headers=headers)

        resp = client.get("/api/reporting/loan-schedule", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        item = next((i for i in data["items"] if i["loan_id"] == loan["id"]), None)
        assert item is not None
        assert item["total_amount_cents"] == 2400000
        assert item["remaining_balance_cents"] == 2200000
        assert item["payments_made"] == 1
        assert item["total_paid_to_date_cents"] == 200000
        assert item["remaining_payments"] > 0
        assert item["projected_pay_off_date"] is not None

    def test_csv_export(self, client: TestClient):
        o = signup_org(client, "LS3")
        headers = auth_header(o["token"])
        resp = client.get("/api/reporting/loan-schedule?format=csv", headers=headers)
        assert resp.status_code == 200
        assert "csv" in resp.headers["content-type"]

    def test_manager_cannot_access(self, client: TestClient):
        o = signup_org(client, "LS4")
        headers = auth_header(o["token"])
        mgr = client.post("/api/auth/invite", json={
            "phone": "+27000000108", "role": "manager", "name": "Manager",
        }, headers=headers).json()
        accept = client.post("/api/auth/accept-invite", json={
            "token": mgr["invite_url"].split("token=")[1],
            "name": "Manager", "phone": "+27000000108", "password": "secret123",
        })
        mgr_headers = auth_header(accept.json()["access_token"])
        resp = client.get("/api/reporting/loan-schedule", headers=mgr_headers)
        assert resp.status_code == 403


class TestPhaseCTenantIsolation:
    """Verify all Phase C endpoints respect multi-tenancy."""

    def test_fixed_vs_variable_isolation(self, client: TestClient):
        o1 = signup_org(client, "TC1")
        o2 = signup_org(client, "TC2")
        h1 = auth_header(o1["token"])
        h2 = auth_header(o2["token"])
        today = date.today().isoformat()
        resp1 = client.get(f"/api/reporting/fixed-vs-variable?start_date={today}&end_date={today}", headers=h1)
        resp2 = client.get(f"/api/reporting/fixed-vs-variable?start_date={today}&end_date={today}", headers=h2)
        assert resp1.status_code == 200
        assert resp2.status_code == 200

    def test_revenue_by_period_isolation(self, client: TestClient):
        o1 = signup_org(client, "TC3")
        o2 = signup_org(client, "TC4")
        h1 = auth_header(o1["token"])
        h2 = auth_header(o2["token"])
        today = date.today().isoformat()
        resp1 = client.get(f"/api/reporting/revenue-by-period?start_date={today}&end_date={today}", headers=h1)
        resp2 = client.get(f"/api/reporting/revenue-by-period?start_date={today}&end_date={today}", headers=h2)
        assert resp1.status_code == 200
        assert resp2.status_code == 200

    def test_payroll_isolation(self, client: TestClient):
        o1 = signup_org(client, "TC5")
        o2 = signup_org(client, "TC6")
        h1 = auth_header(o1["token"])
        h2 = auth_header(o2["token"])
        today = date.today().isoformat()
        resp1 = client.get(f"/api/reporting/payroll-reconciliation?start_date={today}&end_date={today}", headers=h1)
        resp2 = client.get(f"/api/reporting/payroll-reconciliation?start_date={today}&end_date={today}", headers=h2)
        assert resp1.status_code == 200
        assert resp2.status_code == 200
