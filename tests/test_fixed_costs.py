"""Tests for depots, insurance, taxi loans, spare parts, mechanic payments, and fixed-cost reporting."""

from datetime import date, timedelta

from jose import jwt
from fastapi.testclient import TestClient

from app.config import settings


def signup_org(client: TestClient, suffix: str) -> dict:
    resp = client.post(
        "/api/auth/signup",
        json={
            "organisation_name": f"Org {suffix}",
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


class TestDepots:
    def test_owner_create_and_list_depots(self, client: TestClient):
        o = signup_org(client, "D1")
        headers = auth_header(o["token"])

        resp = client.post("/api/depots", json={
            "name": "Thohoyandou Workshop",
            "depot_type": "workshop",
            "address": "Main Road",
        }, headers=headers)
        assert resp.status_code == 201
        depot = resp.json()
        assert depot["name"] == "Thohoyandou Workshop"
        assert depot["depot_type"] == "workshop"

        resp = client.get("/api/depots", headers=headers)
        assert len(resp.json()) == 1

    def test_duplicate_depot_name_rejected(self, client: TestClient):
        o = signup_org(client, "D2")
        headers = auth_header(o["token"])

        client.post("/api/depots", json={"name": "Depot A", "depot_type": "mixed"}, headers=headers)
        resp = client.post("/api/depots", json={"name": "Depot A", "depot_type": "parking"}, headers=headers)
        assert resp.status_code == 409

    def test_owner_update_depot(self, client: TestClient):
        o = signup_org(client, "D3")
        headers = auth_header(o["token"])

        resp = client.post("/api/depots", json={"name": "Old Name", "depot_type": "mixed"}, headers=headers)
        depot_id = resp.json()["id"]

        resp = client.patch(f"/api/depots/{depot_id}", json={
            "name": "New Name",
            "depot_type": "workshop",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_cross_tenant_isolation(self, client: TestClient):
        o1 = signup_org(client, "D4")
        o2 = signup_org(client, "D5")

        resp = client.post("/api/depots", json={"name": "Depot", "depot_type": "mixed"}, headers=auth_header(o1["token"]))
        depot_id = resp.json()["id"]

        resp = client.get("/api/depots", headers=auth_header(o2["token"]))
        assert len(resp.json()) == 0

        resp = client.patch(f"/api/depots/{depot_id}", json={"name": "Hacked"}, headers=auth_header(o2["token"]))
        assert resp.status_code == 404


class TestInsurance:
    def _setup_with_taxi(self, client: TestClient, suffix: str) -> dict:
        o = signup_org(client, suffix)
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, f"CF {suffix}")
        return {"org": o, "headers": headers, "taxi": taxi}

    def test_owner_create_insurance(self, client: TestClient):
        d = self._setup_with_taxi(client, "I1")
        resp = client.post("/api/insurance", json={
            "taxi_id": d["taxi"]["id"],
            "insurer": "Santam",
            "policy_number": "POL123",
            "monthly_premium_cents": 150000,
            "start_date": "2026-01-01",
        }, headers=d["headers"])
        assert resp.status_code == 201
        ins = resp.json()
        assert ins["insurer"] == "Santam"
        assert ins["monthly_premium_cents"] == 150000

    def test_list_insurance_with_taxi(self, client: TestClient):
        d = self._setup_with_taxi(client, "I2")
        client.post("/api/insurance", json={
            "taxi_id": d["taxi"]["id"],
            "insurer": "Santam",
            "monthly_premium_cents": 150000,
            "start_date": "2026-01-01",
        }, headers=d["headers"])

        resp = client.get("/api/insurance", headers=d["headers"])
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["registration_number"] == f"CF I2"

    def test_cross_tenant_isolation(self, client: TestClient):
        d1 = self._setup_with_taxi(client, "I3")
        o2 = signup_org(client, "I4")

        resp = client.post("/api/insurance", json={
            "taxi_id": d1["taxi"]["id"],
            "insurer": "Santam",
            "monthly_premium_cents": 150000,
            "start_date": "2026-01-01",
        }, headers=d1["headers"])
        ins_id = resp.json()["id"]

        resp = client.get("/api/insurance", headers=auth_header(o2["token"]))
        assert len(resp.json()) == 0

        resp = client.patch(f"/api/insurance/{ins_id}", json={
            "monthly_premium_cents": 100,
        }, headers=auth_header(o2["token"]))
        assert resp.status_code == 404


class TestTaxiLoans:
    def _setup_with_taxi(self, client: TestClient, suffix: str) -> dict:
        o = signup_org(client, suffix)
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, f"CF {suffix}")
        return {"org": o, "headers": headers, "taxi": taxi}

    def test_owner_create_loan(self, client: TestClient):
        d = self._setup_with_taxi(client, "L1")
        resp = client.post("/api/taxi-loans", json={
            "taxi_id": d["taxi"]["id"],
            "lender": "WesBank",
            "total_amount_cents": 50000000,
            "remaining_balance_cents": 30000000,
            "monthly_instalment_cents": 850000,
            "start_date": "2026-01-01",
        }, headers=d["headers"])
        assert resp.status_code == 201
        loan = resp.json()
        assert loan["lender"] == "WesBank"
        assert loan["remaining_balance_cents"] == 30000000

    def test_loan_payment_auto_deducts_balance(self, client: TestClient):
        d = self._setup_with_taxi(client, "L2")
        resp = client.post("/api/taxi-loans", json={
            "taxi_id": d["taxi"]["id"],
            "lender": "WesBank",
            "total_amount_cents": 50000000,
            "remaining_balance_cents": 30000000,
            "monthly_instalment_cents": 850000,
            "start_date": "2026-01-01",
        }, headers=d["headers"])
        loan_id = resp.json()["id"]

        resp = client.post(f"/api/taxi-loans/{loan_id}/payments", json={
            "amount_cents": 850000,
            "payment_date": "2026-01-31",
            "reference": "Statement 001",
        }, headers=d["headers"])
        assert resp.status_code == 201

        resp = client.get(f"/api/taxi-loans/{loan_id}/payments", headers=d["headers"])
        assert len(resp.json()) == 1

        resp = client.get("/api/taxi-loans", headers=d["headers"])
        loan = resp.json()[0]
        assert loan["remaining_balance_cents"] == 29150000

    def test_cross_tenant_isolation(self, client: TestClient):
        d1 = self._setup_with_taxi(client, "L3")
        o2 = signup_org(client, "L4")

        resp = client.post("/api/taxi-loans", json={
            "taxi_id": d1["taxi"]["id"],
            "lender": "WesBank",
            "total_amount_cents": 50000000,
            "remaining_balance_cents": 30000000,
            "monthly_instalment_cents": 850000,
            "start_date": "2026-01-01",
        }, headers=d1["headers"])
        loan_id = resp.json()["id"]

        resp = client.get("/api/taxi-loans", headers=auth_header(o2["token"]))
        assert len(resp.json()) == 0

        resp = client.post(f"/api/taxi-loans/{loan_id}/payments", json={
            "amount_cents": 1000,
            "payment_date": "2026-01-31",
        }, headers=auth_header(o2["token"]))
        assert resp.status_code == 404


class TestSparePartPurchases:
    def _setup(self, client: TestClient, suffix: str) -> dict:
        o = signup_org(client, suffix)
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, f"CF {suffix}")
        depot_resp = client.post("/api/depots", json={
            "name": f"Depot {suffix}",
            "depot_type": "workshop",
        }, headers=headers)
        depot = depot_resp.json()
        return {"org": o, "headers": headers, "taxi": taxi, "depot": depot}

    def test_create_spare_part_purchase(self, client: TestClient):
        d = self._setup(client, "S1")
        resp = client.post("/api/spare-parts", json={
            "depot_id": d["depot"]["id"],
            "taxi_id": d["taxi"]["id"],
            "description": "Brake pads",
            "cost_total_cents": 25000,
            "date": "2026-01-15",
        }, headers=d["headers"])
        assert resp.status_code == 201
        assert resp.json()["cost_total_cents"] == 25000

    def test_create_without_taxi(self, client: TestClient):
        d = self._setup(client, "S2")
        resp = client.post("/api/spare-parts", json={
            "depot_id": d["depot"]["id"],
            "description": "General oil stock",
            "cost_total_cents": 50000,
            "date": "2026-01-15",
        }, headers=d["headers"])
        assert resp.status_code == 201
        assert resp.json()["taxi_id"] is None

    def test_cross_tenant_isolation(self, client: TestClient):
        d1 = self._setup(client, "S3")
        o2 = signup_org(client, "S4")

        resp = client.get("/api/spare-parts", headers=auth_header(o2["token"]))
        assert len(resp.json()) == 0


class TestMechanicPayments:
    def _setup(self, client: TestClient, suffix: str) -> dict:
        o = signup_org(client, suffix)
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, f"CF {suffix}")
        depot_resp = client.post("/api/depots", json={
            "name": f"Depot {suffix}",
            "depot_type": "workshop",
        }, headers=headers)
        depot = depot_resp.json()
        return {"org": o, "headers": headers, "taxi": taxi, "depot": depot}

    def test_create_mechanic_payment(self, client: TestClient):
        d = self._setup(client, "M1")
        resp = client.post("/api/mechanic-payments", json={
            "depot_id": d["depot"]["id"],
            "taxi_id": d["taxi"]["id"],
            "mechanic_name": "John The Mechanic",
            "description": "Replaced alternator",
            "amount_cents": 250000,
            "payment_date": "2026-01-20",
            "payment_method": "cash",
        }, headers=d["headers"])
        assert resp.status_code == 201
        assert resp.json()["mechanic_name"] == "John The Mechanic"

    def test_cross_tenant_isolation(self, client: TestClient):
        d1 = self._setup(client, "M2")
        o2 = signup_org(client, "M3")

        resp = client.get("/api/mechanic-payments", headers=auth_header(o2["token"]))
        assert len(resp.json()) == 0


class TestCostOfOperationsIncludesFixedCosts:
    def test_report_includes_all_costs(self, client: TestClient):
        o = signup_org(client, "R1")
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, "CF R1")
        depot = client.post("/api/depots", json={"name": "Depot R1", "depot_type": "workshop"}, headers=headers).json()

        # Fuel cost
        client.post("/api/fuel", json={
            "taxi_id": taxi["id"],
            "date": "2026-01-15",
            "litres": 50.0,
            "cost_total": 120000,
        }, headers=headers)

        # Breakdown cost
        client.post("/api/breakdowns", json={
            "taxi_id": taxi["id"],
            "start_time": "2026-01-10T08:00:00",
            "reason": "Flat tyre",
        }, headers=headers)
        bd_resp = client.get("/api/breakdowns", headers=headers).json()
        bd_id = bd_resp[0]["id"]
        client.patch(f"/api/breakdowns/{bd_id}/close", json={
            "end_time": "2026-01-10T10:00:00",
            "cost_total": 30000,
        }, headers=headers)

        # Insurance
        client.post("/api/insurance", json={
            "taxi_id": taxi["id"],
            "insurer": "Santam",
            "monthly_premium_cents": 150000,
            "start_date": "2026-01-01",
        }, headers=headers)

        # Loan
        loan_resp = client.post("/api/taxi-loans", json={
            "taxi_id": taxi["id"],
            "lender": "WesBank",
            "total_amount_cents": 50000000,
            "remaining_balance_cents": 30000000,
            "monthly_instalment_cents": 850000,
            "start_date": "2026-01-01",
        }, headers=headers).json()
        client.post(f"/api/taxi-loans/{loan_resp['id']}/payments", json={
            "amount_cents": 850000,
            "payment_date": "2026-01-31",
        }, headers=headers)

        # Spare parts
        client.post("/api/spare-parts", json={
            "depot_id": depot["id"],
            "taxi_id": taxi["id"],
            "description": "Brake pads",
            "cost_total_cents": 25000,
            "date": "2026-01-15",
        }, headers=headers)

        # Mechanic payment
        client.post("/api/mechanic-payments", json={
            "depot_id": depot["id"],
            "taxi_id": taxi["id"],
            "mechanic_name": "External Mech",
            "amount_cents": 100000,
            "payment_date": "2026-01-20",
        }, headers=headers)

        resp = client.get("/api/reports/cost-of-operations?start_date=2026-01-01&end_date=2026-01-31", headers=headers)
        assert resp.status_code == 200
        item = resp.json()["items"][0]

        assert item["total_fuel_cost"] == 120000
        assert item["total_breakdown_cost"] == 30000
        assert item["total_insurance_cost"] == 150000
        assert item["total_loan_payment_cost"] == 850000
        assert item["total_spare_part_cost"] == 25000
        assert item["total_mechanic_payment_cost"] == 100000
        assert item["cost_of_operations"] == 1275000

    def test_insurance_pro_rated_for_partial_month(self, client: TestClient):
        o = signup_org(client, "R2")
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, "CF R2")

        client.post("/api/insurance", json={
            "taxi_id": taxi["id"],
            "insurer": "Santam",
            "monthly_premium_cents": 31000,  # R310/month
            "start_date": "2026-01-15",
        }, headers=headers)

        resp = client.get("/api/reports/cost-of-operations?start_date=2026-01-01&end_date=2026-01-31", headers=headers)
        item = resp.json()["items"][0]
        # Jan has 31 days, policy active from 15th = 17 days
        expected = int(31000 * 17 / 31)
        assert item["total_insurance_cost"] == expected

    def test_cross_tenant_cost_isolation(self, client: TestClient):
        o1 = signup_org(client, "R3")
        o2 = signup_org(client, "R4")
        h1 = auth_header(o1["token"])

        taxi = create_taxi(client, h1, "CF R3")
        depot = client.post("/api/depots", json={"name": "Depot R3", "depot_type": "workshop"}, headers=h1).json()

        client.post("/api/fuel", json={
            "taxi_id": taxi["id"],
            "date": "2026-01-15",
            "litres": 50.0,
            "cost_total": 120000,
        }, headers=h1)
        client.post("/api/insurance", json={
            "taxi_id": taxi["id"],
            "insurer": "Santam",
            "monthly_premium_cents": 150000,
            "start_date": "2026-01-01",
        }, headers=h1)

        resp = client.get("/api/reports/cost-of-operations?start_date=2026-01-01&end_date=2026-01-31", headers=auth_header(o2["token"]))
        items = resp.json()["items"]
        assert len(items) == 0


class TestPaymentFrequency:
    def test_weekly_balance_calculation(self, client: TestClient):
        o = signup_org(client, "W1")
        headers = auth_header(o["token"])

        pkg_resp = client.post("/api/remuneration-packages", json={
            "name": "Weekly R2000",
            "base_salary_cents": 200000,
            "payment_frequency": "weekly",
        }, headers=headers)
        pkg = pkg_resp.json()
        assert pkg["payment_frequency"] == "weekly"

        driver_resp = client.post("/api/drivers", json={"name": "Weekly Driver", "phone": "+27000000001"}, headers=headers)
        driver = driver_resp.json()
        employees = client.get("/api/employees", headers=headers).json()
        emp = next(e for e in employees if e["driver_id"] == driver["id"])
        emp = client.patch(f'/api/employees/{emp["id"]}', json={
            "remuneration_package_id": pkg["id"],
            "hire_date": "2026-01-01",
        }, headers=headers).json()

        resp = client.get(
            f"/api/employees/{emp['id']}/balance?start_date=2026-01-01&end_date=2026-01-07",
            headers=headers,
        )
        balance = resp.json()
        assert balance["payment_frequency"] == "weekly"
        assert balance["owed_cents"] == 200000

    def test_monthly_balance_calculation(self, client: TestClient):
        o = signup_org(client, "W2")
        headers = auth_header(o["token"])

        pkg_resp = client.post("/api/remuneration-packages", json={
            "name": "Monthly R8000",
            "base_salary_cents": 800000,
            "payment_frequency": "monthly",
        }, headers=headers)
        pkg = pkg_resp.json()

        driver_resp = client.post("/api/drivers", json={"name": "Monthly Driver", "phone": "+27000000002"}, headers=headers)
        driver = driver_resp.json()
        employees = client.get("/api/employees", headers=headers).json()
        emp = next(e for e in employees if e["driver_id"] == driver["id"])
        emp = client.patch(f'/api/employees/{emp["id"]}', json={
            "remuneration_package_id": pkg["id"],
            "hire_date": "2026-01-01",
        }, headers=headers).json()

        resp = client.get(
            f"/api/employees/{emp['id']}/balance?start_date=2026-01-01&end_date=2026-01-31",
            headers=headers,
        )
        balance = resp.json()
        assert balance["payment_frequency"] == "monthly"
        assert balance["owed_cents"] == 800000


class TestEmployeeDepotAssignment:
    def test_employee_depot_assignment(self, client: TestClient):
        o = signup_org(client, "ED1")
        headers = auth_header(o["token"])

        depot = client.post("/api/depots", json={"name": "Workshop", "depot_type": "workshop"}, headers=headers).json()
        pkg = client.post("/api/remuneration-packages", json={
            "name": "Mechanic salary",
            "base_salary_cents": 500000,
        }, headers=headers).json()
        driver = client.post("/api/drivers", json={"name": "Mechanic Driver", "phone": "+27000000003"}, headers=headers).json()

        employees = client.get("/api/employees", headers=headers).json()
        emp = next(e for e in employees if e["driver_id"] == driver["id"])
        emp = client.patch(f'/api/employees/{emp["id"]}', json={
            "remuneration_package_id": pkg["id"],
            "depot_id": depot["id"],
            "hire_date": "2026-01-01",
        }, headers=headers).json()
        assert emp["depot_id"] == depot["id"]

        resp = client.get("/api/employees", headers=headers)
        item = resp.json()[0]
        assert item["depot_name"] == "Workshop"


class TestDriverAutoEmployee:
    def test_creating_driver_creates_employee_record(self, client: TestClient):
        o = signup_org(client, "AE1")
        headers = auth_header(o["token"])

        driver = client.post("/api/drivers", json={
            "name": "Auto Driver",
            "phone": "+27000000004",
        }, headers=headers).json()

        resp = client.get("/api/employees", headers=headers)
        emps = resp.json()
        assert len(emps) == 1
        assert emps[0]["driver_id"] == driver["id"]
        assert emps[0]["employment_status"] == "active"

    def test_cannot_create_duplicate_employee_for_driver(self, client: TestClient):
        o = signup_org(client, "AE2")
        headers = auth_header(o["token"])

        driver = client.post("/api/drivers", json={
            "name": "Auto Driver 2",
            "phone": "+27000000005",
        }, headers=headers).json()

        resp = client.post("/api/employees", json={
            "driver_id": driver["id"],
            "hire_date": "2026-01-01",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["driver_id"] == driver["id"]
        assert data["hire_date"] == "2026-01-01"
