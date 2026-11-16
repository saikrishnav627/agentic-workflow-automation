from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_low_risk_request_runs_end_to_end():
    r = client.post("/workflows", json={"request": "Onboard Priya Shah to engineering with a standard laptop"})
    body = r.json()
    assert body["status"] == "completed"
    assert all(s["status"] == "done" for s in body["plan"])
    assert any(line.startswith("validator") for line in body["log"])


def test_high_risk_step_pauses_for_human_approval():
    body = client.post("/workflows", json={"request": "Onboard Ravi Kumar and give admin access to prod"}).json()
    assert body["status"] == "awaiting_approval"
    assert body["pending_approval"]["tool"] == "grant_access"
    assert "manager approval" in body["pending_approval"]["policy"]

    done = client.post(f"/workflows/{body['run_id']}/approve", json={"approved": True, "reviewer": "manager"}).json()
    assert done["status"] == "completed"
    admin = next(s for s in done["plan"] if s["tool"] == "grant_access")
    assert admin["approved"] is True and admin["status"] == "done"


def test_rejected_step_is_not_executed():
    body = client.post("/workflows", json={"request": "Order a MacBook Pro laptop for Anna Lee"}).json()
    assert body["status"] == "awaiting_approval"
    done = client.post(f"/workflows/{body['run_id']}/approve", json={"approved": False, "reviewer": "finance"}).json()
    assert done["status"] == "completed_with_rejections"
    order = next(s for s in done["plan"] if s["tool"] == "order_equipment")
    assert order["status"] == "rejected" and "result" not in order


def test_approve_when_not_waiting_returns_409():
    body = client.post("/workflows", json={"request": "Send a welcome email for Mia Chen"}).json()
    r = client.post(f"/workflows/{body['run_id']}/approve", json={"approved": True, "reviewer": "x"})
    assert r.status_code == 409


def test_unknown_run_returns_404():
    assert client.get("/workflows/doesnotexist").status_code == 404
