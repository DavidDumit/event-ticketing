# Architecture Decision Records

## 1. Backend language and framework: Python + Flask
Date: 2026-10-05
Status: Decided
Context: The app is a small server-rendered monolith with two domains, one SQLite database and a few pages for organisers and door volunteers. It has to run as a single process started by one command, and I need to be able to explain every line of it.
Decision: Python with Flask, using the built-in `sqlite3` module instead of an ORM and Jinja templates for the pages.
Alternatives considered: Django: rejected because its ORM, admin and project structure are more than this app needs, and the course grades unnecessary framework weight down. FastAPI: rejected because its main strengths (async, automatic API docs) don't matter for a server-rendered app with low traffic. SQLAlchemy: rejected because plain SQL keeps the schema visible and easy to explain.
Consequences: Fewer dependencies and less magic, so the code is easy to read and test. The cost is writing SQL and request handling by hand, and having no built-in migrations if the schema changes later.

## 3. No foreign key between the check-in and tickets tables
Date: 2026-10-07
Status: Decided
Context: The tickets domain owns `events` and `tickets`, and the check-in domain owns `check_ins`. Check-in needs to refer to tickets, but the two domains should be able to move into separate services with separate databases later.
Decision: `tickets.event_id` is a real foreign key because events and tickets are in the same domain. `check_ins` stores `ticket_code` and `event_id` as plain values with no foreign key, and `UNIQUE (ticket_code)` blocks a second entry with the same ticket.
Alternatives considered: A foreign key from `check_ins.ticket_code` to `tickets.code`: rejected because it ties the two domains together in the database, so splitting them later would mean redesigning the schema. Checking for double entry in Python before inserting: rejected because two volunteers scanning the same code at the same moment could both pass the check, while the UNIQUE constraint makes the database reject the second insert.
Consequences: Check-in can later move to its own database without schema changes. The cost is that SQLite will not stop an unknown code from being stored, so check-in must always call `validate_ticket(code, event_id)` before inserting.
