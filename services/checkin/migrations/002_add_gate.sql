-- Check-in service, migration 002: remember at which gate (door) each ticket was scanned.
-- Runs on a table that already holds check-ins. Adding a NOT NULL column WITH a DEFAULT
-- makes SQL Server fill every existing row with 'main' in the same statement, so old
-- check-ins stay valid and nothing is lost. Applied once, then never edited (ADR-7).
ALTER TABLE check_ins
    ADD gate NVARCHAR(50) NOT NULL CONSTRAINT df_check_ins_gate DEFAULT 'main';
