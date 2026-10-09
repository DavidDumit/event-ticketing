import os
import re
from datetime import datetime, timedelta, timezone

import pytest

from checkin import service
from checkin.service import AlreadyCheckedIn, InvalidTicket

EVENT_ID = 1
DOORS_OPEN = datetime(2026, 12, 1, 20, 0, tzinfo=timezone.utc)

# Fake Tickets domain: code -> what validate_ticket would answer.
TICKETS = {
    "GOOD1": "valid",
    "GOOD2": "valid",
    "GOOD3": "valid",
    "CANCELLED": "cancelled",
    "OTHER_EVENT": "wrong_event",
}


def fake_validate(code, event_id):
    return TICKETS.get(code, "unknown")


def scan(conn, code, now=DOORS_OPEN, event_id=EVENT_ID):
    service.check_in(conn, code, event_id, fake_validate, now=now)


def at(minutes):
    """A time `minutes` after doors open."""
    return DOORS_OPEN + timedelta(minutes=minutes)


# --- check_in -----------------------------------------------------------

def test_valid_ticket_is_checked_in(conn):
    scan(conn, "GOOD1")

    assert service.attendance(conn, EVENT_ID, tickets_sold=1)["checked_in"] == 1


def test_check_in_stores_the_time_in_utc_z_format(conn):
    scan(conn, "GOOD1", now=at(5))

    stored = conn.execute("SELECT checked_in_at FROM check_ins").fetchone()[0]
    assert stored == "2026-12-01T20:05:00Z"


@pytest.mark.parametrize("code, reason", [
    ("CANCELLED", "cancelled"),
    ("OTHER_EVENT", "wrong_event"),
    ("NO_SUCH_CODE", "unknown"),
])
def test_invalid_ticket_is_refused_with_its_reason(conn, code, reason):
    with pytest.raises(InvalidTicket) as error:
        scan(conn, code)

    assert error.value.reason == reason


def test_refused_ticket_is_not_recorded(conn):
    with pytest.raises(InvalidTicket):
        scan(conn, "CANCELLED")

    assert service.attendance(conn, EVENT_ID, tickets_sold=1)["checked_in"] == 0


def test_second_scan_of_same_ticket_is_blocked(conn):
    scan(conn, "GOOD1")

    with pytest.raises(AlreadyCheckedIn):
        scan(conn, "GOOD1")


def test_double_entry_error_gives_time_of_first_check_in(conn):
    scan(conn, "GOOD1", now=at(3))

    with pytest.raises(AlreadyCheckedIn) as error:
        scan(conn, "GOOD1", now=at(40))

    assert error.value.checked_in_at == "2026-12-01T20:03:00Z"


def test_double_entry_does_not_add_a_second_row(conn):
    scan(conn, "GOOD1")
    with pytest.raises(AlreadyCheckedIn):
        scan(conn, "GOOD1")

    assert service.attendance(conn, EVENT_ID, tickets_sold=1)["checked_in"] == 1


def test_spaces_around_the_code_are_ignored(conn):
    scan(conn, "  GOOD1 ")

    with pytest.raises(AlreadyCheckedIn):
        scan(conn, "GOOD1")


def test_validate_receives_the_stripped_code_and_event_id(conn):
    calls = []

    def recording_validate(code, event_id):
        calls.append((code, event_id))
        return "valid"

    service.check_in(conn, " GOOD1\n", 7, recording_validate, now=DOORS_OPEN)

    assert calls == [("GOOD1", 7)]


# --- attendance ---------------------------------------------------------

def test_attendance_counts_check_ins_no_shows_and_rate(conn):
    scan(conn, "GOOD1")
    scan(conn, "GOOD2")
    scan(conn, "GOOD3")

    assert service.attendance(conn, EVENT_ID, tickets_sold=4) == {
        "checked_in": 3, "no_shows": 1, "rate": 75.0,
    }


def test_attendance_only_counts_this_event(conn):
    scan(conn, "GOOD1", event_id=1)
    scan(conn, "GOOD2", event_id=2)

    assert service.attendance(conn, 1, tickets_sold=2)["checked_in"] == 1


def test_attendance_with_no_tickets_sold_has_rate_zero(conn):
    assert service.attendance(conn, EVENT_ID, tickets_sold=0) == {
        "checked_in": 0, "no_shows": 0, "rate": 0,
    }


def test_attendance_rate_is_rounded_to_one_decimal(conn):
    scan(conn, "GOOD1")

    assert service.attendance(conn, EVENT_ID, tickets_sold=3)["rate"] == 33.3


# --- arrivals_by_slot ---------------------------------------------------

def test_arrivals_are_grouped_into_15_minute_slots_in_time_order(conn):
    scan(conn, "GOOD3", now=at(31))   # scanned out of order on purpose
    scan(conn, "GOOD1", now=at(0))
    scan(conn, "GOOD2", now=at(14))

    assert service.arrivals_by_slot(conn, EVENT_ID) == [
        ("2026-12-01T20:00:00Z", 2),
        ("2026-12-01T20:30:00Z", 1),
    ]


def test_arrival_exactly_on_a_slot_boundary_starts_the_new_slot(conn):
    scan(conn, "GOOD1", now=at(15))

    assert service.arrivals_by_slot(conn, EVENT_ID) == [("2026-12-01T20:15:00Z", 1)]


def test_arrivals_for_an_event_without_check_ins_is_empty(conn):
    assert service.arrivals_by_slot(conn, EVENT_ID) == []


# --- domain boundary ----------------------------------------------------

def test_checkin_service_does_not_touch_the_tickets_domain():
    source_file = os.path.join(os.path.dirname(__file__), "..", "checkin", "service.py")
    with open(source_file) as f:
        source = f.read()

    assert not re.search(r"^\s*(from|import)\s+tickets\b", source, re.MULTILINE)
    tables = re.findall(r"\b(?:FROM|JOIN|INTO|UPDATE)\s+(\w+)", source)
    assert tables and set(tables) == {"check_ins"}
