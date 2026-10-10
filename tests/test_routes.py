"""End-to-end tests of the web pages through Flask's test client.

The business rules themselves are tested in test_tickets_service.py and
test_checkin_service.py. These tests check that the pages wire them up.
"""
import re

import pytest

FUTURE = "2030-12-01T20:00"  # datetime-local format, as the browser sends it


def create_event(client, name="Winter Party", capacity=10):
    """Create an event through the form and return its id (read from the redirect)."""
    response = client.post("/events/new", data={
        "name": name, "venue": "Main Hall", "starts_at": FUTURE, "capacity": str(capacity),
    })
    assert response.status_code == 302
    return int(re.search(r"/events/(\d+)$", response.headers["Location"]).group(1))


def sell(client, event_id, email="a@x.com"):
    """Sell a ticket through the form and return its code (read from the flash message)."""
    response = client.post(
        f"/events/{event_id}/tickets",
        data={"holder_name": "Alex", "holder_email": email},
        follow_redirects=True,
    )
    return re.search(r"Ticket code: ([\w-]+)", response.text).group(1)


def cancel(client, code):
    return client.post(f"/tickets/{code}/cancel", follow_redirects=True)


def scan(client, event_id, code):
    return client.post(f"/events/{event_id}/door", data={"code": code}, follow_redirects=True)


# --- basics -------------------------------------------------------------

def test_home_page_loads(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Events" in response.text


def test_health_check_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}


# --- events -------------------------------------------------------------

def test_creating_an_event_redirects_to_its_page(client):
    response = client.post("/events/new", data={
        "name": "Winter Party", "venue": "Main Hall", "starts_at": FUTURE, "capacity": "50",
    }, follow_redirects=True)

    assert response.request.path == "/events/1"
    assert "Winter Party" in response.text
    assert "Event created." in response.text


def test_created_event_is_listed_on_home_page(client):
    create_event(client, name="Winter Party", capacity=50)

    response = client.get("/")

    assert "Winter Party" in response.text
    assert "0 / 50" in response.text


def test_event_form_with_empty_name_shows_error(client):
    response = client.post("/events/new", data={
        "name": "", "venue": "Main Hall", "starts_at": FUTURE, "capacity": "10",
    })

    assert response.status_code == 400
    assert "Name is required." in response.text


def test_event_form_with_zero_capacity_shows_error(client):
    response = client.post("/events/new", data={
        "name": "Party", "venue": "Main Hall", "starts_at": FUTURE, "capacity": "0",
    })

    assert response.status_code == 400
    assert "Capacity must be a whole number greater than 0." in response.text


def test_invalid_event_form_creates_nothing(client):
    client.post("/events/new", data={"name": "", "venue": "", "starts_at": "", "capacity": "0"})

    assert "No events yet." in client.get("/").text


# --- selling and cancelling ---------------------------------------------

def test_selling_a_ticket_shows_its_code(client):
    event_id = create_event(client)

    code = sell(client, event_id)

    assert code in client.get(f"/events/{event_id}").text


def test_selling_past_capacity_shows_sold_out(client):
    event_id = create_event(client, capacity=1)
    sell(client, event_id, "a@x.com")

    response = client.post(
        f"/events/{event_id}/tickets",
        data={"holder_name": "Bo", "holder_email": "b@x.com"},
        follow_redirects=True,
    )

    assert "Sold out" in response.text


def test_cancelling_a_ticket_shows_success_message(client):
    event_id = create_event(client)
    code = sell(client, event_id)

    response = cancel(client, code)

    assert response.request.path == f"/events/{event_id}"
    assert f"Ticket {code} cancelled." in response.text


def test_cancelling_a_ticket_twice_shows_already_cancelled(client):
    event_id = create_event(client)
    code = sell(client, event_id)
    cancel(client, code)

    response = cancel(client, code)

    assert "already cancelled" in response.text


# --- door check-in ------------------------------------------------------

def test_door_page_has_a_focused_code_input(client):
    event_id = create_event(client)

    response = client.get(f"/events/{event_id}/door")

    assert response.status_code == 200
    assert re.search(r'<input id="code"[^>]*autofocus', response.text)


def test_sold_ticket_is_welcomed_at_the_door(client):
    event_id = create_event(client)
    code = sell(client, event_id)

    response = scan(client, event_id, code)

    assert response.request.path == f"/events/{event_id}/door"
    assert "Welcome! Ticket checked in" in response.text


def test_same_ticket_scanned_twice_shows_already_checked_in(client):
    event_id = create_event(client)
    code = sell(client, event_id)
    scan(client, event_id, code)

    response = scan(client, event_id, code)

    assert re.search(r"Already checked in at \d\d:\d\d", response.text)


def test_door_refuses_a_cancelled_ticket(client):
    event_id = create_event(client)
    code = sell(client, event_id)
    cancel(client, code)

    response = scan(client, event_id, code)

    assert "Ticket cancelled: do not let in." in response.text


def test_door_refuses_a_ticket_for_another_event(client):
    event_id = create_event(client, name="Party A")
    other_event_id = create_event(client, name="Party B")
    code = sell(client, other_event_id)

    response = scan(client, event_id, code)

    assert "This ticket is for a different event." in response.text


def test_door_refuses_an_unknown_code(client):
    event_id = create_event(client)

    response = scan(client, event_id, "no-such-code")

    assert "Unknown ticket code." in response.text


def test_door_asks_for_a_code_when_input_is_empty(client):
    event_id = create_event(client)

    response = scan(client, event_id, "   ")

    assert "Type a ticket code." in response.text


# --- report -------------------------------------------------------------

def test_report_shows_checked_in_and_no_show_numbers(client):
    event_id = create_event(client)
    codes = [sell(client, event_id, f"{name}@x.com") for name in ("a", "b", "c", "d")]
    for code in codes[:3]:
        scan(client, event_id, code)

    text = client.get(f"/events/{event_id}/report").text

    assert "<th>Tickets sold</th><td>4</td>" in text
    assert "<th>Checked in</th><td>3</td>" in text
    assert "<th>No-shows</th><td>1</td>" in text
    assert "<th>Attendance rate</th><td>75.0%</td>" in text


def test_report_lists_arrivals_per_slot(client):
    event_id = create_event(client)
    scan(client, event_id, sell(client, event_id))

    text = client.get(f"/events/{event_id}/report").text

    assert "Arrivals per 15 minutes" in text
    assert re.search(r"<td>\d{4}-\d\d-\d\d \d\d:(00|15|30|45) UTC</td><td>1</td>", text)


# --- unknown event ------------------------------------------------------

@pytest.mark.parametrize("url", ["/events/999", "/events/999/door", "/events/999/report"])
def test_pages_for_unknown_event_return_404(client, url):
    assert client.get(url).status_code == 404
