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
