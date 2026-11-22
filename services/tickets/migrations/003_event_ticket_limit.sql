-- Tickets service, migration 003: each event stores its own "max tickets per email" limit
-- (until now a constant of 2 in the code). Runs on a table that already holds events:
-- NOT NULL with DEFAULT 2 fills every existing event with 2 in the same statement, so old
-- events keep exactly the rule they were sold under. Applied once, never edited (ADR-7).
ALTER TABLE events
    ADD max_tickets_per_email INT NOT NULL
        CONSTRAINT df_events_max_tickets_per_email DEFAULT 2
        CONSTRAINT ck_events_max_tickets_per_email CHECK (max_tickets_per_email > 0);
