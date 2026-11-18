-- Check-in service, initial schema (ported from Assignment 1's schema.sql to SQL Server).
-- No foreign keys into the tickets domain: ticket_code and event_id are plain values
-- (ADR-3); the tickets service is asked over HTTP instead.
-- UNIQUE on ticket_code blocks a second entry with the same ticket. Binary collation so
-- codes are compared case-sensitively, exactly like the tickets service stores them.
CREATE TABLE check_ins (
    id             INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_check_ins PRIMARY KEY,
    ticket_code    NVARCHAR(32) COLLATE Latin1_General_100_BIN2 NOT NULL CONSTRAINT uq_check_ins_code UNIQUE,
    event_id       INT          NOT NULL,
    checked_in_at  NVARCHAR(20) NOT NULL
);

CREATE INDEX ix_check_ins_event ON check_ins (event_id, checked_in_at);
