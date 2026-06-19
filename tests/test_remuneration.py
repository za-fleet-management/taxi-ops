"""Tests for remuneration packages, employees, and salary payments."""

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


def create_driver(client: TestClient, headers: dict, name: str = "John Doe", phone: str = "+27123456789") -> dict:
    resp = client.post("/api/drivers", json={
        "name": name,
        "phone": phone,
    }, headers=headers)
    assert resp.status_code == 201
    return resp.json()


class TestRemunerationPackages:
    def test_owner_create_and_list_packages(self, client: TestClient):
        o = signup_org(client, "R1")
        headers = auth_header(o["token"])

        resp = client.post("/api/remuneration-packages", json={
            "name": "Standard R8000/month",
            "base_salary_cents": 800000,
        }, headers=headers)
        assert resp.status_code == 201
        pkg = resp.json()
        assert pkg["name"] == "Standard R8000/month"
        assert pkg["base_salary_cents"] == 800000
        assert pkg["organisation_id"] == o["org_id"]

        resp = client.get("/api/remuneration-packages", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_duplicate_package_name_rejected(self, client: TestClient):
        o = signup_org(client, "R2")
        headers = auth_header(o["token"])

        client.post("/api/remuneration-packages", json={
            "name": "Standard",
            "base_salary_cents": 800000,
        }, headers=headers)

        resp = client.post("/api/remuneration-packages", json={
            "name": "Standard",
            "base_salary_cents": 900000,
        }, headers=headers)
        assert resp.status_code == 409

    def test_owner_update_package(self, client: TestClient):
        o = signup_org(client, "R3")
        headers = auth_header(o["token"])

        resp = client.post("/api/remuneration-packages", json={
            "name": "Basic",
            "base_salary_cents": 500000,
        }, headers=headers)
        pkg_id = resp.json()["id"]

        resp = client.patch(f"/api/remuneration-packages/{pkg_id}", json={
            "base_salary_cents": 600000,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["base_salary_cents"] == 600000

    def test_manager_cannot_create_package(self, client: TestClient):
        from tests.test_phase1 import signup_org as signup_org2, invite_manager, accept_invite

        o = signup_org(client, "R4")
        token = invite_manager(client, o["token"], "R4")
        m = accept_invite(client, token, "R4")
        m_headers = auth_header(m["token"])

        resp = client.post("/api/remuneration-packages", json={
            "name": "Basic",
            "base_salary_cents": 500000,
        }, headers=m_headers)
        assert resp.status_code == 403

    def test_accountant_can_list_packages(self, client: TestClient):
        from tests.test_phase1 import signup_org as signup_org2, invite_manager, accept_invite

        o = signup_org(client, "R5")
        # Create an accountant user via direct invite
        resp = client.post("/api/auth/invite", json={
            "name": "Accountant R5",
            "phone": "+27500000001",
            "role": "accountant",
        }, headers=auth_header(o["token"]))
        token = resp.json()["invite_url"].split("token=")[1]
        resp = client.post("/api/auth/accept-invite", json={
            "token": token,
            "name": "Accountant R5",
            "phone": "+27500000001",
            "password": "secret789",
        })
        a_headers = auth_header(resp.json()["access_token"])

        resp = client.get("/api/remuneration-packages", headers=a_headers)
        assert resp.status_code == 200

    def test_cross_tenant_isolation(self, client: TestClient):
        o1 = signup_org(client, "R6")
        o2 = signup_org(client, "R7")

        resp = client.post("/api/remuneration-packages", json={
            "name": "Package A",
            "base_salary_cents": 800000,
        }, headers=auth_header(o1["token"]))
        pkg_id = resp.json()["id"]

        resp = client.get("/api/remuneration-packages", headers=auth_header(o2["token"]))
        assert len(resp.json()) == 0

        resp = client.patch(f"/api/remuneration-packages/{pkg_id}", json={
            "base_salary_cents": 100,
        }, headers=auth_header(o2["token"]))
        assert resp.status_code == 404


class TestEmployees:
    def _setup_with_pkg(self, client: TestClient, suffix: str) -> dict:
        o = signup_org(client, suffix)
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, f"CF {suffix}")
        driver = create_driver(client, headers, f"Driver {suffix}", f"+27{suffix}1111111")
        pkg_resp = client.post("/api/remuneration-packages", json={
            "name": f"Package {suffix}",
            "base_salary_cents": 800000,
        }, headers=headers)
        pkg = pkg_resp.json()
        return {"org": o, "headers": headers, "taxi": taxi, "driver": driver, "pkg": pkg}

    def test_owner_create_employee(self, client: TestClient):
        d = self._setup_with_pkg(client, "E1")
        resp = client.post("/api/employees", json={
            "driver_id": d["driver"]["id"],
            "remuneration_package_id": d["pkg"]["id"],
            "hire_date": "2026-01-15",
        }, headers=d["headers"])
        assert resp.status_code == 200
        emp = resp.json()
        assert emp["driver_id"] == d["driver"]["id"]
        assert emp["remuneration_package_id"] == d["pkg"]["id"]
        assert emp["employment_status"] == "active"

    def test_duplicate_driver_employee_upserts(self, client: TestClient):
        d = self._setup_with_pkg(client, "E2")
        client.post("/api/employees", json={
            "driver_id": d["driver"]["id"],
            "hire_date": "2026-01-15",
        }, headers=d["headers"])

        resp = client.post("/api/employees", json={
            "driver_id": d["driver"]["id"],
            "hire_date": "2026-02-01",
        }, headers=d["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["hire_date"] == "2026-02-01"

    def test_list_employees_with_details(self, client: TestClient):
        d = self._setup_with_pkg(client, "E3")
        client.post("/api/employees", json={
            "driver_id": d["driver"]["id"],
            "remuneration_package_id": d["pkg"]["id"],
            "hire_date": "2026-01-15",
        }, headers=d["headers"])

        resp = client.get("/api/employees", headers=d["headers"])
        assert resp.status_code == 200
        emps = resp.json()
        assert len(emps) == 1
        assert emps[0]["driver_name"] == f"Driver E3"
        assert emps[0]["package_name"] == f"Package E3"
        assert emps[0]["base_salary_cents"] == 800000

    def test_update_employee_terminate(self, client: TestClient):
        d = self._setup_with_pkg(client, "E4")
        resp = client.post("/api/employees", json={
            "driver_id": d["driver"]["id"],
            "hire_date": "2026-01-15",
        }, headers=d["headers"])
        emp_id = resp.json()["id"]

        resp = client.patch(f"/api/employees/{emp_id}", json={
            "employment_status": "terminated",
            "termination_date": "2026-06-01",
        }, headers=d["headers"])
        assert resp.status_code == 200
        assert resp.json()["employment_status"] == "terminated"
        assert resp.json()["termination_date"] == "2026-06-01"

    def test_accountant_can_list_employees(self, client: TestClient):
        d = self._setup_with_pkg(client, "E5")
        client.post("/api/employees", json={
            "driver_id": d["driver"]["id"],
            "hire_date": "2026-01-15",
        }, headers=d["headers"])

        resp = client.post("/api/auth/invite", json={
            "name": "Accountant E5",
            "phone": "+27500000002",
            "role": "accountant",
        }, headers=auth_header(d["org"]["token"]))
        token = resp.json()["invite_url"].split("token=")[1]
        resp = client.post("/api/auth/accept-invite", json={
            "token": token,
            "name": "Accountant E5",
            "phone": "+27500000002",
            "password": "secret789",
        })
        a_headers = auth_header(resp.json()["access_token"])

        resp = client.get("/api/employees", headers=a_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_manager_cannot_create_employee(self, client: TestClient):
        from tests.test_phase1 import invite_manager, accept_invite

        d = self._setup_with_pkg(client, "E6")
        token = invite_manager(client, d["org"]["token"], "E6m")
        m = accept_invite(client, token, "E6m")
        m_headers = auth_header(m["token"])

        resp = client.post("/api/employees", json={
            "driver_id": d["driver"]["id"],
            "hire_date": "2026-01-15",
        }, headers=m_headers)
        assert resp.status_code == 403

    def test_cross_tenant_isolation(self, client: TestClient):
        d1 = self._setup_with_pkg(client, "E7")
        o2 = signup_org(client, "E8")

        resp = client.post("/api/employees", json={
            "driver_id": d1["driver"]["id"],
            "hire_date": "2026-01-15",
        }, headers=d1["headers"])
        emp_id = resp.json()["id"]

        resp = client.get("/api/employees", headers=auth_header(o2["token"]))
        assert len(resp.json()) == 0

        resp = client.patch(f"/api/employees/{emp_id}", json={
            "employment_status": "terminated",
        }, headers=auth_header(o2["token"]))
        assert resp.status_code == 404


class TestSalaryPayments:
    def _setup_with_emp(self, client: TestClient, suffix: str) -> dict:
        o = signup_org(client, suffix)
        headers = auth_header(o["token"])
        taxi = create_taxi(client, headers, f"CF {suffix}")
        driver = create_driver(client, headers, f"Driver {suffix}", f"+27{suffix}1111111")
        pkg_resp = client.post("/api/remuneration-packages", json={
            "name": f"Package {suffix}",
            "base_salary_cents": 800000,
        }, headers=headers)
        pkg = pkg_resp.json()
        emp_resp = client.post("/api/employees", json={
            "driver_id": driver["id"],
            "remuneration_package_id": pkg["id"],
            "hire_date": "2026-01-01",
        }, headers=headers)
        emp = emp_resp.json()
        return {"org": o, "headers": headers, "taxi": taxi, "driver": driver, "pkg": pkg, "emp": emp}

    def test_owner_create_payment(self, client: TestClient):
        d = self._setup_with_emp(client, "P1")
        resp = client.post("/api/salary-payments", json={
            "employee_id": d["emp"]["id"],
            "amount_cents": 800000,
            "payment_date": "2026-01-31",
            "payment_method": "cash",
            "reference": "January salary",
        }, headers=d["headers"])
        assert resp.status_code == 201
        payment = resp.json()
        assert payment["amount_cents"] == 800000
        assert payment["payment_method"] == "cash"
        assert payment["reference"] == "January salary"

    def test_list_payments(self, client: TestClient):
        d = self._setup_with_emp(client, "P2")
        client.post("/api/salary-payments", json={
            "employee_id": d["emp"]["id"],
            "amount_cents": 800000,
            "payment_date": "2026-01-31",
        }, headers=d["headers"])
        client.post("/api/salary-payments", json={
            "employee_id": d["emp"]["id"],
            "amount_cents": 800000,
            "payment_date": "2026-02-28",
        }, headers=d["headers"])

        resp = client.get("/api/salary-payments", headers=d["headers"])
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_payments_by_employee(self, client: TestClient):
        d = self._setup_with_emp(client, "P3")
        driver2 = create_driver(client, d["headers"], "Driver P3b", "+27300000001")
        emp2_resp = client.post("/api/employees", json={
            "driver_id": driver2["id"],
            "hire_date": "2026-01-01",
        }, headers=d["headers"])
        emp2 = emp2_resp.json()

        client.post("/api/salary-payments", json={
            "employee_id": d["emp"]["id"],
            "amount_cents": 800000,
            "payment_date": "2026-01-31",
        }, headers=d["headers"])
        client.post("/api/salary-payments", json={
            "employee_id": emp2["id"],
            "amount_cents": 500000,
            "payment_date": "2026-01-31",
        }, headers=d["headers"])

        resp = client.get(f"/api/salary-payments?employee_id={d['emp']['id']}", headers=d["headers"])
        assert len(resp.json()) == 1
        assert resp.json()[0]["amount_cents"] == 800000

    def test_filter_payments_by_date(self, client: TestClient):
        d = self._setup_with_emp(client, "P4")
        client.post("/api/salary-payments", json={
            "employee_id": d["emp"]["id"],
            "amount_cents": 800000,
            "payment_date": "2026-01-31",
        }, headers=d["headers"])
        client.post("/api/salary-payments", json={
            "employee_id": d["emp"]["id"],
            "amount_cents": 800000,
            "payment_date": "2026-02-28",
        }, headers=d["headers"])

        resp = client.get("/api/salary-payments?start_date=2026-02-01&end_date=2026-02-28", headers=d["headers"])
        assert len(resp.json()) == 1

    def test_accountant_can_view_payments(self, client: TestClient):
        d = self._setup_with_emp(client, "P5")
        client.post("/api/salary-payments", json={
            "employee_id": d["emp"]["id"],
            "amount_cents": 800000,
            "payment_date": "2026-01-31",
        }, headers=d["headers"])

        resp = client.post("/api/auth/invite", json={
            "name": "Accountant P5",
            "phone": "+27500000003",
            "role": "accountant",
        }, headers=auth_header(d["org"]["token"]))
        token = resp.json()["invite_url"].split("token=")[1]
        resp = client.post("/api/auth/accept-invite", json={
            "token": token,
            "name": "Accountant P5",
            "phone": "+27500000003",
            "password": "secret789",
        })
        a_headers = auth_header(resp.json()["access_token"])

        resp = client.get("/api/salary-payments", headers=a_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_manager_cannot_create_payment(self, client: TestClient):
        from tests.test_phase1 import invite_manager, accept_invite

        d = self._setup_with_emp(client, "P6")
        token = invite_manager(client, d["org"]["token"], "P6m")
        m = accept_invite(client, token, "P6m")
        m_headers = auth_header(m["token"])

        resp = client.post("/api/salary-payments", json={
            "employee_id": d["emp"]["id"],
            "amount_cents": 800000,
            "payment_date": "2026-01-31",
        }, headers=m_headers)
        assert resp.status_code == 403

    def test_cross_tenant_isolation(self, client: TestClient):
        d1 = self._setup_with_emp(client, "P7")
        o2 = signup_org(client, "P8")

        resp = client.post("/api/salary-payments", json={
            "employee_id": d1["emp"]["id"],
            "amount_cents": 800000,
            "payment_date": "2026-01-31",
        }, headers=d1["headers"])
        assert resp.status_code == 201

        resp = client.get("/api/salary-payments", headers=auth_header(o2["token"]))
        assert len(resp.json()) == 0


class TestEmployeeBalance:
    def test_balance_calculation(self, client: TestClient):
        o = signup_org(client, "B1")
        headers = auth_header(o["token"])
        driver = create_driver(client, headers, "Balance Driver", "+27100000001")
        pkg_resp = client.post("/api/remuneration-packages", json={
            "name": "R10000/month",
            "base_salary_cents": 1000000,
        }, headers=headers)
        pkg = pkg_resp.json()
        emp_resp = client.post("/api/employees", json={
            "driver_id": driver["id"],
            "remuneration_package_id": pkg["id"],
            "hire_date": "2026-01-01",
        }, headers=headers)
        emp = emp_resp.json()

        client.post("/api/salary-payments", json={
            "employee_id": emp["id"],
            "amount_cents": 500000,
            "payment_date": "2026-01-31",
        }, headers=headers)

        resp = client.get(
            f"/api/employees/{emp['id']}/balance?start_date=2026-01-01&end_date=2026-01-31",
            headers=headers,
        )
        assert resp.status_code == 200
        balance = resp.json()
        assert balance["owed_cents"] == 1000000
        assert balance["paid_cents"] == 500000
        assert balance["balance_cents"] == 500000

    def test_balance_partial_month_hire(self, client: TestClient):
        o = signup_org(client, "B2")
        headers = auth_header(o["token"])
        driver = create_driver(client, headers, "Partial Driver", "+27100000002")
        pkg_resp = client.post("/api/remuneration-packages", json={
            "name": "R10000/month",
            "base_salary_cents": 1000000,
        }, headers=headers)
        pkg = pkg_resp.json()
        emp_resp = client.post("/api/employees", json={
            "driver_id": driver["id"],
            "remuneration_package_id": pkg["id"],
            "hire_date": "2026-01-15",
        }, headers=headers)
        emp = emp_resp.json()

        resp = client.get(
            f"/api/employees/{emp['id']}/balance?start_date=2026-01-01&end_date=2026-01-31",
            headers=headers,
        )
        assert resp.status_code == 200
        balance = resp.json()
        assert balance["days_employed"] == 17
        assert balance["owed_cents"] == int(1000000 * 17 / 31)

    def test_cross_tenant_balance_blocked(self, client: TestClient):
        o1 = signup_org(client, "B3")
        o2 = signup_org(client, "B4")
        headers1 = auth_header(o1["token"])
        driver = create_driver(client, headers1, "Tenant Driver", "+27100000003")
        emp_resp = client.post("/api/employees", json={
            "driver_id": driver["id"],
            "hire_date": "2026-01-01",
        }, headers=headers1)
        emp = emp_resp.json()

        resp = client.get(
            f"/api/employees/{emp['id']}/balance?start_date=2026-01-01&end_date=2026-01-31",
            headers=auth_header(o2["token"]),
        )
        assert resp.status_code == 404
