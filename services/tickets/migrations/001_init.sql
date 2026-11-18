-- Tickets service, initial schema (ported from Assignment 1's schema.sql to SQL Server).
-- Timestamps stay ISO-8601 UTC text ('2026-12-01T20:00:00Z') so the service code is unchanged.

CREATE TABLE events (
    id          INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_events PRIMARY KEY,
    name        NVARCHAR(200) NOT NULL,
    venue       NVARCHAR(200) NOT NULL,
    starts_at   NVARCHAR(20)  NOT NULL,
    capacity    INT           NOT NULL CONSTRAINT ck_events_capacity CHECK (capacity > 0),
    created_at  NVARCHAR(20)  NOT NULL
);

-- Cancelling sets status = 'cancelled'; rows are never deleted.
-- code uses a binary (case-sensitive) collation: SQL Server compares text
-- case-insensitively by default, which would make 'AbC' and 'abc' the same ticket.
CREATE TABLE tickets (
    id            INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_tickets PRIMARY KEY,
    event_id      INT NOT NULL CONSTRAINT fk_tickets_event REFERENCES events(id),
    code          NVARCHAR(32) COLLATE Latin1_General_100_BIN2 NOT NULL CONSTRAINT uq_tickets_code UNIQUE,
    holder_name   NVARCHAR(200) NOT NULL,
    holder_email  NVARCHAR(320) NOT NULL,
    status        NVARCHAR(10)  NOT NULL CONSTRAINT df_tickets_status DEFAULT 'valid'
                                CONSTRAINT ck_tickets_status CHECK (status IN ('valid', 'cancelled')),
    issued_at     NVARCHAR(20)  NOT NULL
);

CREATE INDEX ix_tickets_event_status ON tickets (event_id, status);
