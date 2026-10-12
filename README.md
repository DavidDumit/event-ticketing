# Event Ticketing & Check-in

A web app for a university student association that runs around 40 events a
semester. **Organisers** create events and sell tickets, and **door volunteers**
type in ticket codes to let people in. After the event, organisers can see who
came and when.

It's a single Flask app with one SQLite database, split into two feature
domains (see `ADR.md`):

| Domain | Folder | What it does | Tables it owns |
|---|---|---|---|
| **Tickets** | `tickets/` | Create events, sell tickets (capacity, max 2 per email, no sales after the start), cancel tickets | `events`, `tickets` |
| **Check-in** | `checkin/` | Check codes at the door, block double entry, attendance report and arrivals per 15 minutes | `check_ins` |

**The seam:** check-in never imports the tickets code or reads its tables. The
only thing that crosses between them is one question,
`validate(code, event_id)` → `"valid" | "cancelled" | "wrong_event" | "unknown"`,
which the check-in route passes into `checkin.service.check_in()`. The route also
reads the event (name and tickets sold) from the tickets domain. In Assignment 2
those two calls become web requests to a separate tickets service.

## Project structure

```
app.py               starts the app (create_app), reads PORT / DATA_DIR / SECRET_KEY
db.py                SQLite connection helpers, creates the tables on startup
schema.sql           all tables (CREATE TABLE IF NOT EXISTS, safe to run every start)
tickets/service.py   tickets business rules (no Flask)
tickets/routes.py    organiser pages
checkin/service.py   check-in business rules (no Flask, no tickets imports)
checkin/routes.py    door and report pages
templates/           HTML pages (Jinja)
tests/               pytest tests
Dockerfile           course template with the four TODOs filled in
```

## Run it directly

Requires Python 3.9+.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open http://localhost:8000. Health check: http://localhost:8000/health.

## Run it with Docker

```bash
docker build -t event-ticketing .
docker run -p 8000:8000 -v event-ticketing-data:/data event-ticketing
```

Then open http://localhost:8000. The database lives in the `event-ticketing-data`
volume, so it survives the container being deleted and started again.

To use another port:

```bash
docker run -e PORT=9000 -p 9000:9000 -v event-ticketing-data:/data event-ticketing
```

## Configuration (environment variables)

Everything is set with environment variables. Nothing needs editing in the code
and no `.env` file is needed.

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Port the server listens on. The app always binds `0.0.0.0`. |
| `DATA_DIR` | `./data` (in Docker: `/data`) | Folder for the SQLite database |
| `SECRET_KEY` | `dev-only-not-secret` | Signs the flash messages. Set your own outside of development. |

**SQLite path:** `$DATA_DIR/app.db`. The folder and tables are created
automatically on first start. On later starts nothing is dropped or re-created,
so existing data is kept. There is no seed data.

## Using the app

1. **Events → New event:** name, venue, start time (UTC) and capacity.
2. On the event page, **sell a ticket** with a name and email. The page shows the ticket code.
3. **Door check-in:** type the code. Green "Welcome!" means let them in; red means don't
   (cancelled, other event, unknown, or already checked in).
4. **Attendance report:** checked in, no-shows, attendance rate and arrivals per 15 minutes.

## Tests & coverage

```bash
pytest --cov=tickets --cov=checkin --cov-report=term-missing
```

Result:

```
63 passed in 0.45s

Name                  Stmts   Miss  Cover   Missing
---------------------------------------------------
checkin/__init__.py       0      0   100%
checkin/routes.py        35      0   100%
checkin/service.py       44      1    98%   66
tickets/__init__.py       0      0   100%
tickets/routes.py        81      8    90%   38, 70-71, 76, 91-92, 119-120
tickets/service.py       81      1    99%   49
---------------------------------------------------
TOTAL                   241     10    96%
```

- `tests/test_tickets_service.py`: tickets business rules
- `tests/test_checkin_service.py`: check-in business rules, using a fake validate function
- `tests/test_routes.py`: the main user flows through the pages with Flask's test client

The business logic (`tickets/service.py` and `checkin/service.py`) is at 98-99%, well above the 70% required. The few lines not covered are rare error paths in the organiser pages (see ADR-4).

## Container contract evidence (§7)

Output of the course checker, `./sdd-assignment-1/container/run.sh ./event-ticketing`:

```
=== SDD Assignment 1 contract check ===
Repository: /Users/daviddumitrescu/Documents/GitHub/event-ticketing

==> Repository shape
  PASS  one Dockerfile, one manifest (requirements.txt)

==> Build from a clean context, no build args
  PASS  image built
  PASS  image size 163 MB

==> Start on PORT=8000 and reach it from the host
  PASS  HTTP 200 from http://localhost:8000/

==> SQLite file under DATA_DIR
  PASS  found in /data: app.db 

==> Data persists, and a second boot does not re-seed
  PASS  volume at /data persists
  WARN  Could not read row counts, skipping the re-seed check.

==> PORT override is honoured (not hardcoded)
  PASS  HTTP 200 from http://localhost:9123/

=== ALL CHECKS PASSED ===
Paste this output into your README as the §7 evidence.
```

About the WARN: the row-count check runs a small Python script on the host
computer, and that script needs Python 3.12. My Mac has an older Python, so the
checker skipped it. The app itself never seeds or drops data on startup: it only
runs `CREATE TABLE IF NOT EXISTS`, so a restart can't change row counts.

## Documentation

- `ADR.md`: the five architecture decisions
- `AI_USAGE.md`: log of how AI was used, and how the accepted code works
