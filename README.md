# Event Ticketing & Check-in

A web app for a student association: organisers create events and issue tickets,
door volunteers check attendees in and see attendance reports.

Two feature domains (see `ADR.md`):
- **Events & Tickets**: events with capacity, tickets with unique codes
- **Check-in**: validate codes at the door, block double entry, attendance reports

## Setup

Requires Python 3.9+.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Then open http://localhost:8000 (health check: http://localhost:8000/health).

## Configuration (environment variables)

| Variable   | Default        | Purpose                                  |
|------------|----------------|------------------------------------------|
| `PORT`     | `8000`         | Port the server listens on (binds `0.0.0.0`) |
| `DATA_DIR` | `./data`       | Folder for the SQLite database            |

The SQLite database is always written to `$DATA_DIR/app.db` and is created
automatically on first start. No manual setup or migration step.

## Tests & coverage

_Coming once the domains are built._
