"""Phase 1 tests: Taxi/Driver CRUD, Income/Breakdown entry, invite flow, tenant isolation."""

from datetime import date, datetime, timezone, timedelta

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


def invite_manager(client: TestClient, owner_token: str, suffix: str) -> str:
    resp = client.post(
        "/api/auth/invite",
        json={"name": f"Manager {suffix}", "phone": f"+27{suffix}9999999"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["invite_url"].split("token=")[1]


def accept_invite(client: TestClient, token: str, suffix: str) -> dict:
    resp = client.post(
        "/api/auth/accept-invite",
        json={
            "token": token,
            "name": f"Manager {suffix}",
            "phone": f"+27{suffix}9999999",
            "password": "secret456",
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


class TestTaxiCRUD:
    def test_owner_create_and_list_taxis(self, client: TestClient):
        o = signup_org(client, "T1")
        headers = auth_header(o["token"])

        resp = client.post("/api/taxis", json={
            "registration_number": "CF 123-456",
            "model": "Toyota Hiace",
        }, headers=headers)
        assert resp.status_code == 201
        taxi = resp.json()
        assert taxi["registration_number"] == "CF 123-456"
        assert taxi["organisation_id"] == o["org_id"]

        resp = client.get("/api/taxis", headers=headers)
        assert len(resp.json()) == 1

    def test_manager_can_list_but_not_create_taxis(self, client: TestClient):
        o = signup_org(client, "T2")
        token = invite_manager(client, o["token"], "T2")
        m = accept_invite(client, token, "T2")

        # manager can list
        resp = client.get("/api/taxis", headers=auth_header(m["token"]))
        assert resp.status_code == 200

        # manager cannot create
        resp = client.post("/api/taxis", json={
            "registration_number": "CF 999-999",
            "model": "Nissan NP200",
        }, headers=auth_header(m["token"]))
        assert resp.status_code == 403

    def test_duplicate_registration_rejected(self, client: TestClient):
        o = signup_org(client, "T3")
        headers = auth_header(o["token"])
        client.post("/api/taxis", json={
            "registration_number": "CF 111-111",
            "model": "Ford Ranger",
        }, headers=headers)
        resp = client.post("/api/taxis", json={
            "registration_number": "CF 111-111",
            "model": "Ford Ranger",
        }, headers=headers)
        assert resp.status_code == 409

    def test_update_taxi(self, client: TestClient):
        o = signup_org(client, "T4")
        headers = auth_header(o["token"])
        create = client.post("/api/taxis", json={
            "registration_number": "CF 777-777",
            "model": "VW Caddy",
        }, headers=headers).json()

        resp = client.patch(f"/api/taxis/{create['id']}", json={
            "status": "breakdown",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "breakdown"

    def test_cross_tenant_taxi_isolation(self, client: TestClient):
        a = signup_org(client, "XA")
        b = signup_org(client, "XB")
        ta = client.post("/api/taxis", json={
            "registration_number": "AA 123",
            "model": "Car A",
        }, headers=auth_header(a["token"])).json()

        # B cannot see A's taxi
        resp = client.get("/api/taxis", headers=auth_header(b["token"]))
        ids = [t["id"] for t in resp.json()]
        assert ta["id"] not in ids

        # B cannot update A's taxi
        resp = client.patch(f"/api/taxis/{ta['id']}", json={
            "status": "retired",
        }, headers=auth_header(b["token"]))
        assert resp.status_code == 404


class TestDriverCRUD:
    def test_owner_create_and_list_drivers(self, client: TestClient):
        o = signup_org(client, "D1")
        headers = auth_header(o["token"])

        resp = client.post("/api/drivers", json={
            "name": "John Doe",
            "phone": "+27710000001",
        }, headers=headers)
        assert resp.status_code == 201
        driver = resp.json()
        assert driver["name"] == "John Doe"
        assert driver["organisation_id"] == o["org_id"]

        resp = client.get("/api/drivers", headers=headers)
        assert len(resp.json()) == 1

    def test_manager_cannot_create_drivers(self, client: TestClient):
        o = signup_org(client, "D2")
        token = invite_manager(client, o["token"], "D2")
        m = accept_invite(client, token, "D2")

        resp = client.post("/api/drivers", json={
            "name": "Jane",
            "phone": "+27710000002",
        }, headers=auth_header(m["token"]))
        assert resp.status_code == 403

    def test_assign_taxi_to_driver(self, client: TestClient):
        o = signup_org(client, "D3")
        headers = auth_header(o["token"])
        taxi = client.post("/api/taxis", json={
            "registration_number": "CF 333",
            "model": "Taxi",
        }, headers=headers).json()
        driver = client.post("/api/drivers", json={
            "name": "Bob",
            "phone": "+27710000003",
        }, headers=headers).json()

        resp = client.patch(f"/api/drivers/{driver['id']}", json={
            "assigned_taxi_id": taxi["id"],
        }, headers=headers)
        assert resp.json()["assigned_taxi_id"] == taxi["id"]

    def test_cross_tenant_driver_isolation(self, client: TestClient):
        a = signup_org(client, "XDA")
        b = signup_org(client, "XDB")
        da = client.post("/api/drivers", json={
            "name": "Alice",
            "phone": "+27710000004",
        }, headers=auth_header(a["token"])).json()

        resp = client.get("/api/drivers", headers=auth_header(b["token"]))
        ids = [d["id"] for d in resp.json()]
        assert da["id"] not in ids


class TestIncome:
    def test_owner_create_and_list_income(self, client: TestClient):
        o = signup_org(client, "I1")
        headers = auth_header(o["token"])
        taxi = client.post("/api/taxis", json={
            "registration_number": "CF I01",
            "model": "M",
        }, headers=headers).json()
        driver = client.post("/api/drivers", json={
            "name": "I Driver",
            "phone": "+2771000010",
        }, headers=headers).json()

        resp = client.post("/api/income", json={
            "taxi_id": taxi["id"],
            "driver_id": driver["id"],
            "date": "2026-06-18",
            "total_cash": 15000,
        }, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["total_cash"] == 15000

        resp = client.get("/api/income", headers=headers)
        assert len(resp.json()) == 1

    def test_manager_can_create_income(self, client: TestClient):
        o = signup_org(client, "I2")
        token = invite_manager(client, o["token"], "I2")
        m = accept_invite(client, token, "I2")
        headers_m = auth_header(m["token"])

        taxi = client.post("/api/taxis", json={
            "registration_number": "CF I02",
            "model": "M",
        }, headers=auth_header(o["token"])).json()
        driver = client.post("/api/drivers", json={
            "name": "M Driver",
            "phone": "+2771000011",
        }, headers=auth_header(o["token"])).json()

        resp = client.post("/api/income", json={
            "taxi_id": taxi["id"],
            "driver_id": driver["id"],
            "date": "2026-06-18",
            "total_cash": 20000,
        }, headers=headers_m)
        assert resp.status_code == 201

    def test_manager_cannot_list_income(self, client: TestClient):
        o = signup_org(client, "I3")
        token = invite_manager(client, o["token"], "I3")
        m = accept_invite(client, token, "I3")
        resp = client.get("/api/income", headers=auth_header(m["token"]))
        assert resp.status_code == 403

    def test_idempotent_client_uuid(self, client: TestClient):
        o = signup_org(client, "I4")
        headers = auth_header(o["token"])
        taxi = client.post("/api/taxis", json={
            "registration_number": "CF I04",
            "model": "M",
        }, headers=headers).json()
        driver = client.post("/api/drivers", json={
            "name": "ID Driver",
            "phone": "+2771000012",
        }, headers=headers).json()

        uid = "test-client-uuid-12345"
        payload = {
            "id": uid,
            "taxi_id": taxi["id"],
            "driver_id": driver["id"],
            "date": "2026-06-18",
            "total_cash": 5000,
        }
        r1 = client.post("/api/income", json=payload, headers=headers)
        r2 = client.post("/api/income", json=payload, headers=headers)
        assert r1.status_code == 201
        assert r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"] == uid

    def test_cross_tenant_income_isolation(self, client: TestClient):
        a = signup_org(client, "XIA")
        b = signup_org(client, "XIB")
        taxi = client.post("/api/taxis", json={
            "registration_number": "CF XIA",
            "model": "M",
        }, headers=auth_header(a["token"])).json()
        driver = client.post("/api/drivers", json={
            "name": "XA Driver",
            "phone": "+2771000013",
        }, headers=auth_header(a["token"])).json()
        income = client.post("/api/income", json={
            "taxi_id": taxi["id"],
            "driver_id": driver["id"],
            "date": "2026-06-18",
            "total_cash": 5000,
        }, headers=auth_header(a["token"])).json()

        resp = client.get("/api/income", headers=auth_header(b["token"]))
        ids = [i["id"] for i in resp.json()]
        assert income["id"] not in ids


class TestBreakdown:
    def test_create_and_close_breakdown(self, client: TestClient):
        o = signup_org(client, "B1")
        headers = auth_header(o["token"])
        taxi = client.post("/api/taxis", json={
            "registration_number": "CF B01",
            "model": "M",
        }, headers=headers).json()

        now = datetime.now(timezone.utc).isoformat()
        resp = client.post("/api/breakdowns", json={
            "taxi_id": taxi["id"],
            "start_time": now,
            "reason": "Engine failure",
        }, headers=headers)
        assert resp.status_code == 201
        bd = resp.json()
        assert bd["end_time"] is None

        # Close the breakdown
        later = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        resp = client.patch(f"/api/breakdowns/{bd['id']}/close", json={
            "end_time": later,
            "cost_total": 500000,
            "parts_used": '["engine","gasket"]',
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["end_time"] is not None
        assert resp.json()["cost_total"] == 500000

    def test_manager_can_create_and_close_breakdown(self, client: TestClient):
        o = signup_org(client, "B2")
        token = invite_manager(client, o["token"], "B2")
        m = accept_invite(client, token, "B2")
        headers_m = auth_header(m["token"])

        taxi = client.post("/api/taxis", json={
            "registration_number": "CF B02",
            "model": "M",
        }, headers=auth_header(o["token"])).json()

        now = datetime.now(timezone.utc).isoformat()
        resp = client.post("/api/breakdowns", json={
            "taxi_id": taxi["id"],
            "start_time": now,
        }, headers=headers_m)
        assert resp.status_code == 201

        later = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        resp = client.patch(f"/api/breakdowns/{resp.json()['id']}/close", json={
            "end_time": later,
            "cost_total": 10000,
        }, headers=headers_m)
        assert resp.status_code == 200

    def test_manager_cannot_list_breakdowns(self, client: TestClient):
        o = signup_org(client, "B3")
        token = invite_manager(client, o["token"], "B3")
        m = accept_invite(client, token, "B3")
        resp = client.get("/api/breakdowns", headers=auth_header(m["token"]))
        assert resp.status_code == 403

    def test_idempotent_client_uuid(self, client: TestClient):
        o = signup_org(client, "B4")
        headers = auth_header(o["token"])
        taxi = client.post("/api/taxis", json={
            "registration_number": "CF B04",
            "model": "M",
        }, headers=headers).json()

        uid = "breakdown-uuid-test"
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "id": uid,
            "taxi_id": taxi["id"],
            "start_time": now,
        }
        r1 = client.post("/api/breakdowns", json=payload, headers=headers)
        r2 = client.post("/api/breakdowns", json=payload, headers=headers)
        assert r1.status_code == 201
        assert r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"] == uid

    def test_cross_tenant_breakdown_isolation(self, client: TestClient):
        a = signup_org(client, "XBA")
        b = signup_org(client, "XBB")
        taxi = client.post("/api/taxis", json={
            "registration_number": "CF XBA",
            "model": "M",
        }, headers=auth_header(a["token"])).json()
        bd = client.post("/api/breakdowns", json={
            "taxi_id": taxi["id"],
            "start_time": datetime.now(timezone.utc).isoformat(),
        }, headers=auth_header(a["token"])).json()

        # B cannot see A's breakdowns
        resp = client.get("/api/breakdowns", headers=auth_header(b["token"]))
        ids = [b["id"] for b in resp.json()]
        assert bd["id"] not in ids

        # B cannot close A's breakdown
        later = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        resp = client.patch(f"/api/breakdowns/{bd['id']}/close", json={
            "end_time": later,
            "cost_total": 100,
        }, headers=auth_header(b["token"]))
        assert resp.status_code == 404


class TestInviteFlow:
    def test_full_invite_flow(self, client: TestClient):
        o = signup_org(client, "INV1")
        token = invite_manager(client, o["token"], "INV1")

        resp = client.post("/api/auth/accept-invite", json={
            "token": token,
            "name": "New Manager",
            "phone": "+27123456789",
            "password": "managerpass",
        })
        assert resp.status_code == 200

        # Manager can log in
        resp = client.post("/api/auth/login", json={
            "phone": "+27123456789",
            "password": "managerpass",
        })
        assert resp.status_code == 200

    def test_expired_invite_rejected(self, client: TestClient):
        o = signup_org(client, "INV2")
        resp = client.post("/api/auth/invite", json={
            "name": "Late",
            "phone": "+27999999999",
        }, headers=auth_header(o["token"]))
        token = resp.json()["invite_url"].split("token=")[1]

        from datetime import datetime, timezone, timedelta
        from app.models.invite import InviteToken
        from tests.conftest import TestSessionLocal
        db = TestSessionLocal()
        invite = db.query(InviteToken).filter(InviteToken.token == token).first()
        invite.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
        db.close()

        resp = client.post("/api/auth/accept-invite", json={
            "token": token,
            "name": "Late Manager",
            "phone": "+27999999999",
            "password": "latepass",
        })
        assert resp.status_code == 400

    def test_used_invite_rejected(self, client: TestClient):
        o = signup_org(client, "INV3")
        token = invite_manager(client, o["token"], "INV3")
        accept_invite(client, token, "INV3")

        resp = client.post("/api/auth/accept-invite", json={
            "token": token,
            "name": "Dup Manager",
            "phone": "+27888888888",
            "password": "duppass",
        })
        assert resp.status_code == 400

    def test_only_owner_can_invite(self, client: TestClient):
        o = signup_org(client, "INV4")
        token = invite_manager(client, o["token"], "INV4")
        m = accept_invite(client, token, "INV4")

        resp = client.post("/api/auth/invite", json={
            "name": "Should Fail",
            "phone": "+27777777777",
        }, headers=auth_header(m["token"]))
        assert resp.status_code == 403
