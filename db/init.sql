-- Local only: creates one database and one login per service.
-- Idempotent: safe to run on every `docker compose up` (it checks before creating).
-- Passwords are NOT in this file: they come in as sqlcmd variables from .env.
-- On Azure the logins are created once during the initial setup instead.

IF DB_ID('tickets') IS NULL CREATE DATABASE tickets;
GO
IF DB_ID('checkin') IS NULL CREATE DATABASE checkin;
GO

-- Logins: create if missing, otherwise just update the password from .env
IF SUSER_ID('tickets_user') IS NULL
    CREATE LOGIN tickets_user WITH PASSWORD = '$(TICKETS_DB_PASSWORD)', DEFAULT_DATABASE = tickets;
ELSE
    ALTER LOGIN tickets_user WITH PASSWORD = '$(TICKETS_DB_PASSWORD)';
GO
IF SUSER_ID('checkin_user') IS NULL
    CREATE LOGIN checkin_user WITH PASSWORD = '$(CHECKIN_DB_PASSWORD)', DEFAULT_DATABASE = checkin;
ELSE
    ALTER LOGIN checkin_user WITH PASSWORD = '$(CHECKIN_DB_PASSWORD)';
GO

-- Each login becomes a user in its OWN database only, so it has no access to the other one.
-- ddladmin lets its migrations create and change tables; reader/writer for the data.
USE tickets;
IF USER_ID('tickets_user') IS NULL CREATE USER tickets_user FOR LOGIN tickets_user;
ALTER ROLE db_ddladmin ADD MEMBER tickets_user;
ALTER ROLE db_datareader ADD MEMBER tickets_user;
ALTER ROLE db_datawriter ADD MEMBER tickets_user;
GO

USE checkin;
IF USER_ID('checkin_user') IS NULL CREATE USER checkin_user FOR LOGIN checkin_user;
ALTER ROLE db_ddladmin ADD MEMBER checkin_user;
ALTER ROLE db_datareader ADD MEMBER checkin_user;
ALTER ROLE db_datawriter ADD MEMBER checkin_user;
GO
