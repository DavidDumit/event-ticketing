-- Every statement uses IF NOT EXISTS so init_db() can run on every startup.
-- Timestamps are ISO-8601 TEXT, e.g. '2026-10-06T19:30:00Z'.

-- =====================================================================
-- Tickets domain: events and the tickets issued for them
-- =====================================================================

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    venue       TEXT    NOT NULL,
    starts_at   TEXT    NOT NULL,
    capacity    INTEGER NOT NULL CHECK (capacity > 0),
    created_at  TEXT    NOT NULL
);

-- Cancelling a ticket sets status = 'cancelled'; rows are never deleted.
CREATE TABLE IF NOT EXISTS tickets (
    id            INTEGER PRIMARY KEY,
    event_id      INTEGER NOT NULL REFERENCES events(id),
    code          TEXT    NOT NULL UNIQUE,
    holder_name   TEXT    NOT NULL,
    holder_email  TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'valid'
                          CHECK (status IN ('valid', 'cancelled')),
    issued_at     TEXT    NOT NULL
);

-- =====================================================================
-- Check-in domain: ticket codes scanned at the door
-- =====================================================================

-- No foreign keys into the tickets domain on purpose: ticket_code and
-- event_id are plain values, so check-in could move to its own database.
-- UNIQUE on ticket_code is what blocks a second entry with the same ticket.
CREATE TABLE IF NOT EXISTS check_ins (
    id             INTEGER PRIMARY KEY,
    ticket_code    TEXT    NOT NULL UNIQUE,
    event_id       INTEGER NOT NULL,
    checked_in_at  TEXT    NOT NULL
);
