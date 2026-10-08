"""Business logic for the Tickets domain. Plain sqlite3, no Flask."""
import secrets
from datetime import datetime, timezone

MAX_TICKETS_PER_EMAIL = 2


class TicketError(Exception):
    """Base class for every Tickets domain error."""


class EventNotFound(TicketError):
    pass


class SalesClosed(TicketError):
    pass


class SoldOut(TicketError):
    pass


class TicketLimitReached(TicketError):
    pass


class TicketNotFound(TicketError):
    pass


class TicketAlreadyCancelled(TicketError):
    pass


def _now():
    return datetime.now(timezone.utc)


def _to_iso(dt):
    """datetime -> '2026-10-06T19:30:00Z' (UTC), the format schema.sql uses."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _from_iso(text):
    """ISO-8601 text -> aware UTC datetime. Python 3.9 can't parse a trailing 'Z'."""
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:  # no offset given: treat it as UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def create_event(conn, name, venue, starts_at, capacity):
    """Store a new event and return its id. capacity > 0 is enforced by schema.sql."""
    starts_at = _to_iso(_from_iso(starts_at))  # normalise so every stored time looks the same
    with conn:
        cur = conn.execute(
            "INSERT INTO events (name, venue, starts_at, capacity, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, venue, starts_at, capacity, _to_iso(_now())),
        )
    return cur.lastrowid


def issue_ticket(conn, event_id, holder_name, holder_email, now=None):
    """Sell one ticket and return its code, or raise a TicketError explaining why not."""
    now = now or _now()
    holder_email = holder_email.strip().lower()  # 'A@x.com' and 'a@x.com' count as the same holder

    # Take the write lock before counting, so two sales at once can't both
    # see the last free seat and oversell the event.
    conn.execute("BEGIN IMMEDIATE")
    try:
        event = conn.execute(
            "SELECT starts_at, capacity FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        if event is None:
            raise EventNotFound(event_id)

        if now >= _from_iso(event[0]):
            raise SalesClosed(event_id)

        sold = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE event_id = ? AND status = 'valid'", (event_id,)
        ).fetchone()[0]
        if sold >= event[1]:
            raise SoldOut(event_id)

        held = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE event_id = ? AND holder_email = ? AND status = 'valid'",
            (event_id, holder_email),
        ).fetchone()[0]
        if held >= MAX_TICKETS_PER_EMAIL:
            raise TicketLimitReached(holder_email)

        code = secrets.token_urlsafe(8)
        conn.execute(
            "INSERT INTO tickets (event_id, code, holder_name, holder_email, status, issued_at) "
            "VALUES (?, ?, ?, ?, 'valid', ?)",
            (event_id, code, holder_name, holder_email, _to_iso(now)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return code


def cancel_ticket(conn, code):
    """Mark a ticket as cancelled. The row is kept, never deleted."""
    with conn:
        cur = conn.execute(
            "UPDATE tickets SET status = 'cancelled' WHERE code = ? AND status = 'valid'", (code,)
        )
    if cur.rowcount == 0:
        # Nothing changed: either the code doesn't exist or it was already cancelled
        if conn.execute("SELECT 1 FROM tickets WHERE code = ?", (code,)).fetchone():
            raise TicketAlreadyCancelled(code)
        raise TicketNotFound(code)


def validate_ticket(conn, code, event_id):
    """Return 'valid', 'cancelled', 'wrong_event' or 'unknown' for a scanned code."""
    ticket = conn.execute(
        "SELECT event_id, status FROM tickets WHERE code = ?", (code,)
    ).fetchone()
    if ticket is None:
        return "unknown"
    if ticket[0] != event_id:
        return "wrong_event"
    return ticket[1]  # 'valid' or 'cancelled', guaranteed by the CHECK in schema.sql


# --- Read-only helpers for the pages -------------------------------------

def _dicts(cur):
    """Rows as plain dicts, whatever row_factory the connection uses."""
    columns = [c[0] for c in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


_EVENTS_WITH_SOLD = (
    "SELECT e.id, e.name, e.venue, e.starts_at, e.capacity, "
    "(SELECT COUNT(*) FROM tickets t WHERE t.event_id = e.id AND t.status = 'valid') AS sold "
    "FROM events e"
)


def list_events(conn):
    """All events, soonest first, each with how many valid tickets are sold."""
    return _dicts(conn.execute(_EVENTS_WITH_SOLD + " ORDER BY e.starts_at, e.id"))


def get_event(conn, event_id):
    """One event (same fields as list_events), or None."""
    rows = _dicts(conn.execute(_EVENTS_WITH_SOLD + " WHERE e.id = ?", (event_id,)))
    return rows[0] if rows else None


def list_tickets(conn, event_id):
    """All tickets for an event, cancelled ones included, oldest first."""
    return _dicts(conn.execute(
        "SELECT code, holder_name, holder_email, status, issued_at "
        "FROM tickets WHERE event_id = ? ORDER BY issued_at, id",
        (event_id,),
    ))


def get_ticket(conn, code):
    """One ticket as a dict (including its event_id), or None."""
    rows = _dicts(conn.execute(
        "SELECT code, event_id, holder_name, holder_email, status, issued_at "
        "FROM tickets WHERE code = ?",
        (code,),
    ))
    return rows[0] if rows else None
