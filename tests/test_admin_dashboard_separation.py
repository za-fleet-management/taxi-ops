from jose import jwt

from app.config import settings


def signup_owner(client, suffix: str) -> dict:
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


def test_dashboard_shell_does_not_expose_admin_navigation(client):
    owner = signup_owner(client, "DASH")

    resp = client.get("/dashboard", headers=auth_header(owner["token"]))
    assert resp.status_code == 200, resp.text
    assert "/partials/admin/" not in resp.text
    assert 'href="/admin"' not in resp.text
    assert "Administration" not in resp.text


def test_dashboard_sidebar_keeps_operator_links(client):
    owner = signup_owner(client, "LINKS")

    resp = client.get("/dashboard", headers=auth_header(owner["token"]))
    assert resp.status_code == 200, resp.text

    expected_links = [
        '/dashboard',
        '/income/new',
        '/breakdowns/new',
        '/fuel/new',
        '/taxis',
        '/drivers',
        '/routes',
        '/depots',
        '/insurance',
        '/loans',
        '/spare-parts/new',
        '/mechanic-payments/new',
        '/remuneration',
        '/employees',
        '/salary/new',
        '/reports',
        '/reports/executive-summary',
        '/reports/fixed-vs-variable',
        '/reports/revenue-by-period',
        '/reports/payroll-reconciliation',
        '/reports/asset-register',
        '/reports/loan-schedule',
        '/users',
        '/subscription',
    ]
    for href in expected_links:
        assert f'href="{href}"' in resp.text


def test_admin_shell_is_standalone(client):
    owner = signup_owner(client, "ADMIN")

    resp = client.get("/admin", headers=auth_header(owner["token"]))
    assert resp.status_code == 200, resp.text
    assert 'href="/dashboard"' not in resp.text
    assert "/income/new" not in resp.text
    assert "/breakdowns/new" not in resp.text
    assert "/fuel/new" not in resp.text
    assert "Standalone admin" in resp.text


def test_admin_page_redirects_to_admin_login_when_unauthenticated(client):
    resp = client.get("/admin", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/admin/login"
