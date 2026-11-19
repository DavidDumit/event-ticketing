# Event Ticketing & Check-in

A web app for a university student association: organisers create events and
sell tickets, door volunteers check people in and see attendance reports.

> **Assignment 2 in progress.** The Assignment 1 monolith has been split into two
> services along the seam from ADR-2. This is the initial services structure;
> SQL Server, migrations, CI/CD and the Azure deployment come next.

## Structure

| Folder | What it is | Owns |
|---|---|---|
| `services/tickets/` | Tickets service: events, selling, cancelling, ticket validation (JSON API) | its own database: `events`, `tickets` |
| `services/checkin/` | Check-in service: door check-ins and attendance reports (JSON API) | its own database: `check_ins` |
| `ui/` | Static UI (one HTML page + `config.js`), served by nginx locally; calls both services from the browser | — |

Each service has its own `Dockerfile`, `requirements.txt`, schema and tests.

**The seam.** Check-in never reads the tickets database. It calls the tickets
service over HTTP (`tickets_client.py`) for two things:
`GET /tickets/{code}/validate?event_id=` and `GET /events/{id}`.
Every call has a timeout (`TICKETS_TIMEOUT_S`). If tickets is down, a check-in
returns `503 TicketsUnavailable` and the report degrades to check-in's own numbers.

## Run the whole system

Once, create your local `.env` with your own passwords (it is gitignored, never commit it):

```bash
cp .env.example .env     # then edit the three passwords
```

Then:

```bash
docker compose up --build
```

Compose starts SQL Server, runs `db/init.sql` once (the `db-init` job: one database and one
login per service, idempotent), then the two services and the UI. On Apple Silicon, enable
*Use Rosetta for x86_64/amd64 emulation* in Docker Desktop for the SQL Server image.

| URL | What |
|---|---|
| http://localhost:8080 | UI: create events, issue and cancel tickets, door check-in, attendance report, health of both services |
| http://localhost:8001/health | Tickets service |
| http://localhost:8002/health | Check-in service |

Partial failure: `docker compose stop tickets`, then check-in still answers
`/health` with 200 and check-ins return a clear 503.

## Run one service without Docker

```bash
cd services/tickets            # or services/checkin
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PORT=8001 python app.py        # check-in: PORT=8002 TICKETS_URL=http://localhost:8001 python app.py
```

## Configuration (environment variables)

| Variable | Service | Default | Purpose |
|---|---|---|---|
| `PORT` | both | `8000` | Port the service listens on (binds `0.0.0.0`) |
| `UI_ORIGIN` | both | `http://localhost:8080` | The only origin allowed by CORS |
| `GIT_SHA` | both | `dev` | Version reported by `/health` |
| `DATABASE_URL` | both | none, required (secret) | `mssql+pymssql://user:password@host:1433/db` of the service's own database; pending migrations in `migrations/` run on startup |
| `DB_CONNECT_ATTEMPTS` | both | `8` | Connection retries with backoff (1, 2, 4, 8, 15 s...) while SQL Server or a paused Azure SQL database wakes up |
| `TICKETS_URL` | checkin | `http://localhost:8001` | Base URL of the tickets service (`http://tickets:8000` in compose) |
| `TICKETS_TIMEOUT_S` | checkin | `2` | Timeout in seconds for calls to tickets |

## Tests and coverage (per service)

The tests run against a real SQL Server test database (`tickets_test` / `checkin_test`,
created by `db/init.sql`), never against the app's databases or Azure. With compose running:

```bash
cd services/tickets && TEST_DATABASE_URL="mssql+pymssql://sa:<MSSQL_SA_PASSWORD>@localhost:1433/tickets_test" pytest --cov=tickets --cov-report=term-missing
cd services/checkin && TEST_DATABASE_URL="mssql+pymssql://sa:<MSSQL_SA_PASSWORD>@localhost:1433/checkin_test" pytest --cov=checkin --cov-report=term-missing
```

In CI each job starts its own throwaway SQL Server container with a random password.

## Migrations

Each service owns its schema in `services/<name>/migrations/NNN_name.sql`. On startup the
service applies, in order and each in its own transaction, every file not yet listed in its
`schema_migrations` table. Applied files are never edited: a change is always a new file.

## Documentation

- `ADR.md`: architecture decisions (1-5 from Assignment 1)
- `AI_USAGE.md`: how AI was used, and how the accepted code works
