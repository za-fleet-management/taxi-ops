"""Phase 3 tests: Fuel CRUD, Route CRUD, route tagging on income, cost-of-operations, route-profitability."""

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


def seed_base(client: TestClient, token: str, suffix: str):
    """Create taxi, driver, route for use in Phase 3 tests."""
    t = client.post("/api/taxis", json={"registration_number": f"PH3 {suffix}", "model": "Hiace"},
                    headers=auth(token)).json()
    d = client.post("/api/drivers", json={"name": f"Driver {suffix}", "phone": f"+27{suffix}1111111"},
                    headers=auth(token)).json()
    r = client.post("/api/routes", json={"name": f"Route {suffix}", "distance_km": 15.5},
                    headers=auth(token)).json()
    return t, d, r


class TestFuelCRUD:
    def test_owner_and_manager_can_create_fuel(self, client: TestClient):
        o = signup_org(client, "F1")
        t, _, _ = seed_base(client, o["token"], "F1")
        m = invite_manager(client, o["token"], "F1")
        today = date.today().isoformat()
        for token, label in [(o["token"], "owner"), (m["token"], "manager")]:
            resp = client.post("/api/fuel", json={
                "taxi_id": t["id"], "date": today, "litres": 45.5, "cost_total": 45500,
            }, headers=auth(token))
            assert resp.status_code == 201, f"{label} failed"
            assert resp.json()["cost_total"] == 45500

    def test_owner_can_list_fuel(self, client: TestClient):
        o = signup_org(client, "F2")
        t, _, _ = seed_base(client, o["token"], "F2")
        today = date.today().isoformat()
        client.post("/api/fuel", json={
            "taxi_id": t["id"], "date": today, "litres": 40, "cost_total": 40000,
        }, headers=auth(o["token"]))
        resp = client.get("/api/fuel", headers=auth(o["token"]))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_manager_cannot_list_fuel(self, client: TestClient):
        o = signup_org(client, "F3")
        m = invite_manager(client, o["token"], "F3")
        resp = client.get("/api/fuel", headers=auth(m["token"]))
        assert resp.status_code == 403

    def test_cross_tenant_isolation(self, client: TestClient):
        a = signup_org(client, "F4A")
        b = signup_org(client, "F4B")
        ta, _, _ = seed_base(client, a["token"], "F4A")
        tb, _, _ = seed_base(client, b["token"], "F4B")
        today = date.today().isoformat()
        client.post("/api/fuel", json={"taxi_id": ta["id"], "date": today, "litres": 10, "cost_total": 1000},
                    headers=auth(a["token"]))
        client.post("/api/fuel", json={"taxi_id": tb["id"], "date": today, "litres": 20, "cost_total": 2000},
                    headers=auth(b["token"]))
        resp_b = client.get("/api/fuel", headers=auth(b["token"]))
        assert len(resp_b.json()) == 1
        assert resp_b.json()[0]["cost_total"] == 2000


class TestRouteCRUD:
    def test_owner_create_and_list_routes(self, client: TestClient):
        o = signup_org(client, "R1")
        resp = client.post("/api/routes", json={"name": "Test Route", "distance_km": 12.3},
                           headers=auth(o["token"]))
        assert resp.status_code == 201
        route_id = resp.json()["id"]
        resp2 = client.get("/api/routes", headers=auth(o["token"]))
        ids = [r["id"] for r in resp2.json()]
        assert route_id in ids

    def test_manager_can_list_routes(self, client: TestClient):
        o = signup_org(client, "R2")
        client.post("/api/routes", json={"name": "Manager Visible"}, headers=auth(o["token"]))
        m = invite_manager(client, o["token"], "R2")
        resp = client.get("/api/routes", headers=auth(m["token"]))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_manager_cannot_create_route(self, client: TestClient):
        o = signup_org(client, "R3")
        m = invite_manager(client, o["token"], "R3")
        resp = client.post("/api/routes", json={"name": "Should Fail"}, headers=auth(m["token"]))
        assert resp.status_code == 403


class TestRouteTagging:
    def test_income_with_route_tag(self, client: TestClient):
        o = signup_org(client, "T1")
        t, d, rt = seed_base(client, o["token"], "T1")
        today = date.today().isoformat()
        resp = client.post("/api/income", json={
            "taxi_id": t["id"], "driver_id": d["id"], "date": today,
            "total_cash": 50000, "route_id": rt["id"],
        }, headers=auth(o["token"]))
        assert resp.status_code == 201

    def test_income_without_route_tag_still_works(self, client: TestClient):
        o = signup_org(client, "T2")
        t, d, _ = seed_base(client, o["token"], "T2")
        today = date.today().isoformat()
        resp = client.post("/api/income", json={
            "taxi_id": t["id"], "driver_id": d["id"], "date": today,
            "total_cash": 30000,
        }, headers=auth(o["token"]))
        assert resp.status_code == 201


class TestCostOfOperations:
    def test_owner_can_access(self, client: TestClient):
        o = signup_org(client, "C1")
        t, d, _ = seed_base(client, o["token"], "C1")
        today = date.today().isoformat()
        client.post("/api/income", json={"taxi_id": t["id"], "driver_id": d["id"],
                    "date": today, "total_cash": 100000}, headers=auth(o["token"]))
        client.post("/api/fuel", json={"taxi_id": t["id"], "date": today,
                    "litres": 20, "cost_total": 20000}, headers=auth(o["token"]))
        resp = client.get("/api/reports/cost-of-operations", headers=auth(o["token"]))
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["total_income"] == 100000
        assert items[0]["total_fuel_cost"] == 20000
        assert items[0]["cost_of_operations"] == 20000
        assert items[0]["net_position"] == 80000

    def test_manager_cannot_access(self, client: TestClient):
        o = signup_org(client, "C2")
        m = invite_manager(client, o["token"], "C2")
        resp = client.get("/api/reports/cost-of-operations", headers=auth(m["token"]))
        assert resp.status_code == 403


class TestRouteProfitability:
    def test_owner_can_access(self, client: TestClient):
        o = signup_org(client, "P1")
        t, d, rt = seed_base(client, o["token"], "P1")
        today = date.today().isoformat()
        client.post("/api/income", json={"taxi_id": t["id"], "driver_id": d["id"],
                    "date": today, "total_cash": 80000, "route_id": rt["id"]},
                    headers=auth(o["token"]))
        resp = client.get("/api/reports/route-profitability", headers=auth(o["token"]))
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1
        assert items[0]["total_income"] == 80000
        assert items[0]["allocation_note"] != ""

    def test_manager_cannot_access(self, client: TestClient):
        o = signup_org(client, "P2")
        m = invite_manager(client, o["token"], "P2")
        resp = client.get("/api/reports/route-profitability", headers=auth(m["token"]))
        assert resp.status_code == 403
