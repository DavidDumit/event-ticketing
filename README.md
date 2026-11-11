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
| `ui/` | Static UI (placeholder), served by nginx locally | — |

Each service has its own `Dockerfile`, `requirements.txt`, schema and tests.

**The seam.** Check-in never reads the tickets database. It calls the tickets
service over HTTP (`tickets_client.py`) for two things:
`GET /tickets/{code}/validate?event_id=` and `GET /events/{id}`.
Every call has a timeout (`TICKETS_TIMEOUT_S`). If tickets is down, a check-in
returns `503 TicketsUnavailable` and the report degrades to check-in's own numbers.

## Run the whole system

```bash
docker compose up --build
```

| URL | What |
|---|---|
| http://localhost:8080 | UI (shows both services' health) |
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
| `DATA_DIR` | both | `./data` (`/data` in Docker) | Folder for the service's own SQLite file |
| `UI_ORIGIN` | both | `http://localhost:8080` | The only origin allowed by CORS |
| `GIT_SHA` | both | `dev` | Version reported by `/health` |
| `TICKETS_URL` | checkin | `http://localhost:8001` | Base URL of the tickets service (`http://tickets:8000` in compose) |
| `TICKETS_TIMEOUT_S` | checkin | `2` | Timeout in seconds for calls to tickets |

## Tests and coverage (per service)

```bash
cd services/tickets && pytest --cov=tickets --cov-report=term-missing
cd services/checkin && pytest --cov=checkin --cov-report=term-missing
```

## Documentation

- `ADR.md`: architecture decisions (1-5 from Assignment 1)
- `AI_USAGE.md`: how AI was used, and how the accepted code works
