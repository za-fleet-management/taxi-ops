"""Phase 2 tests: reporting endpoints (income-summary, driver-performance, downtime-cost)."""

from datetime import date, datetime, timezone, timedelta

from jose import jwt
from fastapi.testclient import TestClient

from app.config import settings


def signup_org(client: TestClient, suffix: str) -> dict:
    resp = client.post(
        "/api/auth/signup", json={
            "organisation_name": f"Org {suffix}", "region": "Gauteng",
            "name": f"Owner {suffix}", "phone": f"+27{suffix}0000000",
            "password": "secret123",
        },
    )
    data = resp.json()
    payload = jwt.decode(data["access_token"], settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return {"token": data["access_token"], "org_id": payload["organisation_id"]}


def invite_manager(client: TestClient, owner_token: str, suffix: str) -> dict:
    t = client.post("/api/auth/invite", json={"name": f"Mgr {suffix}", "phone": f"+27{suffix}9999999"},
                    headers={"Authorization": f"Bearer {owner_token}"}).json()["invite_url"].split("token=")[1]
    m = client.post("/api/auth/accept-invite", json={"token": t, "name": f"Mgr {suffix}",
                    "phone": f"+27{suffix}9999999", "password": "p"}).json()
    payload = jwt.decode(m["access_token"], settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return {"token": m["access_token"], "org_id": payload["organisation_id"]}


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def seed_data(client: TestClient, token: str, org_id: str, n_taxis: int = 3, n_drivers: int = 2):
    """Create taxis, drivers, income entries, and a breakdown for testing."""
    taxis = []
    for i in range(n_taxis):
        r = client.post("/api/taxis", json={"registration_number": f"RP {i:03d}", "model": "Hiace"},
                        headers=auth(token))
        taxis.append(r.json())

    drivers = []
    for i in range(n_drivers):
        r = client.post("/api/drivers", json={"name": f"Driver {i}", "phone": f"+27{i}00000000"},
                        headers=auth(token))
        drivers.append(r.json())

    today = date.today()
    for i, taxi in enumerate(taxis):
        driver = drivers[i % len(drivers)]
        client.post("/api/income", json={
            "taxi_id": taxi["id"], "driver_id": driver["id"],
            "date": today.isoformat(), "total_cash": 10000 + i * 1000,
        }, headers=auth(token))
        client.post("/api/income", json={
            "taxi_id": taxi["id"], "driver_id": driver["id"],
            "date": (today - timedelta(days=1)).isoformat(), "total_cash": 8000,
        }, headers=auth(token))

    # One breakdown
    now = datetime.now(timezone.utc)
    bd = client.post("/api/breakdowns", json={
        "taxi_id": taxis[0]["id"], "start_time": now.isoformat(),
    }, headers=auth(token)).json()
    client.patch(f"/api/breakdowns/{bd['id']}/close", json={
        "end_time": (now + timedelta(hours=3)).isoformat(),
        "cost_total": 150000,
    }, headers=auth(token))

    return taxis, drivers


class TestIncomeSummary:
    def test_owner_can_access(self, client: TestClient):
        o = signup_org(client, "R1")
        seed_data(client, o["token"], o["org_id"])
        resp = client.get("/api/reports/income-summary", headers=auth(o["token"]))
        assert resp.status_code == 200
        body = resp.json()
        assert body["grand_total"] > 0
        assert len(body["items"]) >= 2

    def test_manager_cannot_access(self, client: TestClient):
        o = signup_org(client, "R2")
        m = invite_manager(client, o["token"], "R2")
        resp = client.get("/api/reports/income-summary", headers=auth(m["token"]))
        assert resp.status_code == 403

    def test_filter_by_date_range(self, client: TestClient):
        o = signup_org(client, "R3")
        seed_data(client, o["token"], o["org_id"])
        today = date.today()
        resp = client.get(f"/api/reports/income-summary?start_date={today.isoformat()}&end_date={today.isoformat()}",
                          headers=auth(o["token"]))
        assert resp.status_code == 200
        assert resp.json()["grand_total"] > 0

    def test_cross_tenant_isolation(self, client: TestClient):
        a = signup_org(client, "R4A")
        b = signup_org(client, "R4B")
        seed_data(client, a["token"], a["org_id"])
        # Org B gets one taxi with different income so totals differ
        resp = client.post("/api/taxis", json={"registration_number": "XX 001", "model": "Hiace"},
                           headers=auth(b["token"]))
        taxi_b = resp.json()
        resp = client.post("/api/drivers", json={"name": "Driver B", "phone": "+27000000001"},
                           headers=auth(b["token"]))
        driver_b = resp.json()
        today = date.today().isoformat()
        client.post("/api/income", json={"taxi_id": taxi_b["id"], "driver_id": driver_b["id"],
                    "date": today, "total_cash": 1}, headers=auth(b["token"]))
        resp_a = client.get("/api/reports/income-summary", headers=auth(a["token"]))
        resp_b = client.get("/api/reports/income-summary", headers=auth(b["token"]))
        assert resp_a.json()["grand_total"] != resp_b.json()["grand_total"]


class TestDriverPerformance:
    def test_owner_can_access(self, client: TestClient):
        o = signup_org(client, "R5")
        seed_data(client, o["token"], o["org_id"])
        resp = client.get("/api/reports/driver-performance", headers=auth(o["token"]))
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) > 0
        for item in body["items"]:
            assert item["total_income_cents"] > 0

    def test_manager_cannot_access(self, client: TestClient):
        o = signup_org(client, "R6")
        m = invite_manager(client, o["token"], "R6")
        resp = client.get("/api/reports/driver-performance", headers=auth(m["token"]))
        assert resp.status_code == 403


class TestDowntimeCost:
    def test_owner_can_access(self, client: TestClient):
        o = signup_org(client, "R7")
        seed_data(client, o["token"], o["org_id"])
        resp = client.get("/api/reports/downtime-cost", headers=auth(o["token"]))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_cost"] >= 150000
        assert len(body["items"]) > 0

    def test_manager_cannot_access(self, client: TestClient):
        o = signup_org(client, "R8")
        m = invite_manager(client, o["token"], "R8")
        resp = client.get("/api/reports/downtime-cost", headers=auth(m["token"]))
        assert resp.status_code == 403

    def test_duration_computed(self, client: TestClient):
        o = signup_org(client, "R9")
        seed_data(client, o["token"], o["org_id"])
        resp = client.get("/api/reports/downtime-cost", headers=auth(o["token"]))
        item = resp.json()["items"][0]
        assert item["duration_hours"] == 3.0

    def test_cross_tenant_isolation(self, client: TestClient):
        a = signup_org(client, "R10A")
        b = signup_org(client, "R10B")
        seed_data(client, a["token"], a["org_id"])
        resp_a = client.get("/api/reports/downtime-cost", headers=auth(a["token"]))
        resp_b = client.get("/api/reports/downtime-cost", headers=auth(b["token"]))
        assert resp_a.json()["total_cost"] > 0
        assert resp_b.json()["total_cost"] == 0
