from datetime import datetime, timedelta, timezone

import pytest

from tickets import service
from tickets.service import (
    EventNotFound,
    SalesClosed,
    SoldOut,
    TicketLimitReached,
    TicketNotFound,
)

STARTS_AT = datetime(2026, 12, 1, 20, 0, tzinfo=timezone.utc)
BEFORE_START = STARTS_AT - timedelta(days=7)


def make_event(conn, capacity=10):
    return service.create_event(conn, "Winter Party", "Main Hall", "2026-12-01T20:00:00Z", capacity)


def buy(conn, event_id, email="a@x.com", now=BEFORE_START):
    return service.issue_ticket(conn, event_id, "Alex", email, now=now)


def ticket_status(conn, code):
    row = conn.execute("SELECT status FROM tickets WHERE code = ?", (code,)).fetchone()
    return row[0] if row else None


# --- create_event -------------------------------------------------------

def test_create_event_stores_the_event(conn):
    event_id = make_event(conn, capacity=50)

    row = conn.execute(
        "SELECT name, venue, capacity FROM events WHERE id = ?", (event_id,)
    ).fetchone()
    assert row == ("Winter Party", "Main Hall", 50)


def test_create_event_normalises_starts_at_to_utc_z_format(conn):
    event_id = service.create_event(conn, "Party", "Hall", "2026-12-01T21:00:00+01:00", 10)

    starts_at = conn.execute("SELECT starts_at FROM events WHERE id = ?", (event_id,)).fetchone()[0]
    assert starts_at == "2026-12-01T20:00:00Z"


# --- issue_ticket -------------------------------------------------------

def test_issue_ticket_returns_a_code_for_a_valid_ticket(conn):
    event_id = make_event(conn)

    code = buy(conn, event_id)

    assert code
    assert service.validate_ticket(conn, code, event_id) == "valid"


def test_two_tickets_get_different_codes(conn):
    event_id = make_event(conn)

    assert buy(conn, event_id, "a@x.com") != buy(conn, event_id, "b@x.com")


def test_sold_out_when_capacity_is_reached(conn):
    event_id = make_event(conn, capacity=2)
    buy(conn, event_id, "a@x.com")
    buy(conn, event_id, "b@x.com")

    with pytest.raises(SoldOut):
        buy(conn, event_id, "c@x.com")


def test_cancelled_ticket_frees_its_seat(conn):
    event_id = make_event(conn, capacity=1)
    code = buy(conn, event_id, "a@x.com")
    service.cancel_ticket(conn, code)

    assert buy(conn, event_id, "b@x.com")


def test_third_ticket_for_same_email_is_refused(conn):
    event_id = make_event(conn)
    buy(conn, event_id, "a@x.com")
    buy(conn, event_id, "a@x.com")

    with pytest.raises(TicketLimitReached):
        buy(conn, event_id, "a@x.com")


def test_ticket_limit_ignores_email_capitalisation(conn):
    event_id = make_event(conn)
    buy(conn, event_id, "A@x.com")
    buy(conn, event_id, "a@X.COM")

    with pytest.raises(TicketLimitReached):
        buy(conn, event_id, "a@x.com")


def test_sales_closed_exactly_at_start_time(conn):
    event_id = make_event(conn)

    with pytest.raises(SalesClosed):
        buy(conn, event_id, now=STARTS_AT)


def test_sales_closed_after_start_time(conn):
    event_id = make_event(conn)

    with pytest.raises(SalesClosed):
        buy(conn, event_id, now=STARTS_AT + timedelta(hours=1))


def test_sale_allowed_one_second_before_start(conn):
    event_id = make_event(conn)

    assert buy(conn, event_id, now=STARTS_AT - timedelta(seconds=1))


def test_issue_ticket_for_unknown_event_raises_event_not_found(conn):
    with pytest.raises(EventNotFound):
        buy(conn, event_id=999)


def test_refused_sale_does_not_store_a_ticket(conn):
    event_id = make_event(conn, capacity=1)
    buy(conn, event_id, "a@x.com")

    with pytest.raises(SoldOut):
        buy(conn, event_id, "b@x.com")

    assert conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 1


# --- cancel_ticket ------------------------------------------------------

def test_cancel_ticket_sets_status_to_cancelled(conn):
    event_id = make_event(conn)
    code = buy(conn, event_id)

    service.cancel_ticket(conn, code)

    assert ticket_status(conn, code) == "cancelled"


def test_cancel_ticket_keeps_the_row(conn):
    event_id = make_event(conn)
    code = buy(conn, event_id)

    service.cancel_ticket(conn, code)

    assert conn.execute("SELECT COUNT(*) FROM tickets WHERE code = ?", (code,)).fetchone()[0] == 1


def test_cancel_unknown_code_raises_ticket_not_found(conn):
    with pytest.raises(TicketNotFound):
        service.cancel_ticket(conn, "no-such-code")


# --- validate_ticket ----------------------------------------------------

def test_validate_returns_valid_for_a_sold_ticket(conn):
    event_id = make_event(conn)
    code = buy(conn, event_id)

    assert service.validate_ticket(conn, code, event_id) == "valid"


def test_validate_returns_cancelled_for_a_cancelled_ticket(conn):
    event_id = make_event(conn)
    code = buy(conn, event_id)
    service.cancel_ticket(conn, code)

    assert service.validate_ticket(conn, code, event_id) == "cancelled"


def test_validate_returns_wrong_event_for_another_events_ticket(conn):
    event_id = make_event(conn)
    other_event_id = make_event(conn)
    code = buy(conn, event_id)

    assert service.validate_ticket(conn, code, other_event_id) == "wrong_event"


def test_validate_returns_unknown_for_an_unknown_code(conn):
    event_id = make_event(conn)

    assert service.validate_ticket(conn, "no-such-code", event_id) == "unknown"
