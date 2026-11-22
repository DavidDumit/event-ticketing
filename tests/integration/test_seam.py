"""Integration tests across the seam: the real check-in service calling the real tickets
service over HTTP, both with their own SQL Server database (started with docker compose).

Run with compose up (CI does this in the "integration" job):
  TICKETS_URL=http://localhost:8001 CHECKIN_URL=http://localhost:8002 pytest tests/integration -m "not tickets_down"
  docker compose stop tickets
  TICKETS_URL=... CHECKIN_URL=... pytest tests/integration -m tickets_down
"""
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

import pytest

TICKETS = os.environ.get("TICKETS_URL", "")
CHECKIN = os.environ.get("CHECKIN_URL", "")

pytestmark = pytest.mark.skipif(not (TICKETS and CHECKIN), reason="TICKETS_URL and CHECKIN_URL not set")


def call(method, url, body=None):
    """(status, json body) for one HTTP request; HTTP errors are returned, not raised."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


@pytest.fixture(scope="module")
def event():
    """A fresh event with two tickets, created through the tickets service."""
    starts = (datetime.now(UTC) + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    status, body = call("POST", f"{TICKETS}/events",
                        {"name": "Seam test", "venue": "CI", "starts_at": starts, "capacity": 10})
    assert status == 201
    event_id = body["id"]
    codes = []
    for name in ("Ana", "Bo"):
        status, body = call("POST", f"{TICKETS}/events/{event_id}/tickets",
                            {"holder_name": name, "holder_email": f"{name.lower()}@example.com"})
        assert status == 201
        codes.append(body["code"])
    return {"id": event_id, "codes": codes}


@pytest.mark.tickets_up
def test_valid_ticket_checks_in_through_the_tickets_service(event):
    url = f"{CHECKIN}/events/{event['id']}/checkins"
    status, body = call("POST", url, {"code": event["codes"][0], "gate": "North"})

    assert status == 201
    assert body["status"] == "checked_in"


@pytest.mark.tickets_up
def test_second_scan_is_refused_with_time_and_gate(event):
    status, body = call("POST", f"{CHECKIN}/events/{event['id']}/checkins", {"code": event["codes"][0]})

    assert status == 409
    assert body["error"] == "AlreadyCheckedIn"
    assert body["gate"] == "North"


@pytest.mark.tickets_up
def test_ticket_cancelled_in_tickets_is_refused_at_the_door(event):
    status, _ = call("POST", f"{TICKETS}/tickets/{event['codes'][1]}/cancel")
    assert status == 200

    status, body = call("POST", f"{CHECKIN}/events/{event['id']}/checkins", {"code": event["codes"][1]})

    assert status == 409
    assert body == {"error": "InvalidTicket", "reason": "cancelled"}


@pytest.mark.tickets_up
def test_unknown_code_is_refused(event):
    status, body = call("POST", f"{CHECKIN}/events/{event['id']}/checkins", {"code": "NOT-A-TICKET"})

    assert status == 409
    assert body["reason"] == "unknown"


@pytest.mark.tickets_up
def test_report_combines_both_services(event):
    status, body = call("GET", f"{CHECKIN}/events/{event['id']}/report")

    assert status == 200
    assert body["tickets_sold"] == 1          # from tickets: one valid ticket left after the cancel
    assert body["checked_in"] == 1            # from check-in's own database
    assert body["rate"] == 100.0
    assert body["by_gate"] == {"North": 1}


@pytest.mark.tickets_down
def test_check_in_returns_503_when_tickets_is_down():
    status, body = call("POST", f"{CHECKIN}/events/1/checkins", {"code": "ANY"})

    assert status == 503
    assert body["error"] == "TicketsUnavailable"


@pytest.mark.tickets_down
def test_report_degrades_when_tickets_is_down():
    status, body = call("GET", f"{CHECKIN}/events/1/report")

    assert status == 200
    assert body["tickets_sold"] is None
    assert "notice" in body


@pytest.mark.tickets_down
def test_check_in_health_does_not_depend_on_tickets():
    status, body = call("GET", f"{CHECKIN}/health")

    assert status == 200
    assert body["status"] == "ok"
