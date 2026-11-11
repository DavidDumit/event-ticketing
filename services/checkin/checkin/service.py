"""Business logic for the Check-in domain. Plain sqlite3, no Flask.

This module only touches the check_ins table and never imports tickets/.
The Tickets domain is reached through the `validate(code, event_id)` function
the caller passes in, so it can later be swapped for an HTTP call.
"""
import sqlite3
from datetime import datetime, timezone


class CheckInError(Exception):
    """Base class for every Check-in domain error."""


class InvalidTicket(CheckInError):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason  # 'cancelled', 'wrong_event' or 'unknown'


class AlreadyCheckedIn(CheckInError):
    def __init__(self, code, checked_in_at):
        super().__init__(f"{code} already checked in at {checked_in_at}")
        self.code = code
        self.checked_in_at = checked_in_at


# Same helpers as tickets/service.py, copied on purpose: importing them would
# couple the two domains.
def _now():
    return datetime.now(timezone.utc)


def _to_iso(dt):
    """datetime -> '2026-10-06T19:30:00Z' (UTC), the format schema.sql uses."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _from_iso(text):
    """'...Z' text -> aware UTC datetime. Python 3.9 can't parse a trailing 'Z'."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def check_in(conn, code, event_id, validate, now=None):
    """Let a ticket in, or raise InvalidTicket / AlreadyCheckedIn."""
    code = code.strip()
    now = now or _now()

    status = validate(code, event_id)
    if status != "valid":
        raise InvalidTicket(status)

    # No "already used?" SELECT first: two volunteers scanning at the same
    # moment could both pass it. The UNIQUE constraint on ticket_code decides.
    try:
        with conn:
            conn.execute(
                "INSERT INTO check_ins (ticket_code, event_id, checked_in_at) VALUES (?, ?, ?)",
                (code, event_id, _to_iso(now)),
            )
    except sqlite3.IntegrityError:
        first = conn.execute(
            "SELECT checked_in_at FROM check_ins WHERE ticket_code = ?", (code,)
        ).fetchone()
        if first is None:  # some other constraint failed, not a double entry
            raise
        raise AlreadyCheckedIn(code, first[0])


def attendance(conn, event_id, tickets_sold):
    """Checked in, no-shows and attendance rate (%) for an event.

    tickets_sold comes from the caller because that number belongs to the
    Tickets domain.
    """
    checked_in = conn.execute(
        "SELECT COUNT(*) FROM check_ins WHERE event_id = ?", (event_id,)
    ).fetchone()[0]
    return {
        "checked_in": checked_in,
        "no_shows": max(tickets_sold - checked_in, 0),
        "rate": round(checked_in / tickets_sold * 100, 1) if tickets_sold else 0,
    }


def arrivals_by_slot(conn, event_id, minutes=15):
    """Check-ins per time slot, e.g. [('2026-12-01T20:00:00Z', 4), ...], in time order.

    `minutes` should divide 60 (5, 10, 15, 30...). Slots with no arrivals are left out.
    """
    rows = conn.execute(
        "SELECT checked_in_at FROM check_ins WHERE event_id = ? ORDER BY checked_in_at",
        (event_id,),
    ).fetchall()

    slots = {}  # dicts keep insertion order, and rows are already sorted
    for (checked_in_at,) in rows:
        dt = _from_iso(checked_in_at)
        slot = dt.replace(minute=dt.minute // minutes * minutes, second=0, microsecond=0)
        key = _to_iso(slot)
        slots[key] = slots.get(key, 0) + 1
    return list(slots.items())
