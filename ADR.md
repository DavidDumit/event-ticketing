# Architecture Decision Records

## 1. Backend language and framework: Python + Flask
Date: 2026-10-05
Status: Decided
Context: I needed to pick a language and framework for a small web app with two parts (tickets and check-in), one SQLite database and a few simple pages. It has to start with one command, and I have to be able to explain all of the code myself in the comprehension check.
Decision: I went with Python and Flask, because Python is the language I'm most comfortable with. I use Python's built-in `sqlite3` module to talk to the database and Jinja templates for the pages.
Alternatives considered: Django, but it comes with a lot of things I don't need (an admin panel, its own way of handling the database, a fixed project structure), and the assignment says picking it without a reason counts as poor judgement. FastAPI, but it's mainly good for building APIs and fast async apps, and my app is just a few HTML pages with not much traffic. I also looked at SQLAlchemy for the database, but writing plain SQL means I can see exactly what's happening and explain it more easily.
Consequences: The project stays small and easy to follow, with only a few packages. The downside is that I have to write the SQL myself, and if I change the database structure later there's no automatic tool to update it.

## 3. No foreign key between the check-in and tickets tables
Date: 2026-10-07
Status: Decided
Context: The tickets part of the app owns the `events` and `tickets` tables, and the check-in part owns the `check_ins` table. Check-in needs to know which ticket was scanned, but in Assignment 2 the two parts should be able to become separate services, each with its own database.
Decision: Inside the tickets part, `tickets.event_id` is a normal foreign key to `events`, since both tables belong together. But `check_ins` just stores the ticket code and event id as plain values, with no link to the tickets table. I also made `ticket_code` UNIQUE in `check_ins`, so the same ticket can't be checked in twice.
Alternatives considered: Linking `check_ins` to `tickets` with a foreign key. I didn't do this because it would tie the two parts together in the database, and splitting them later would mean redesigning the tables. I also thought about stopping double entry with an "already used?" check in Python before saving, but if two volunteers scan the same ticket at the exact same moment, both checks could pass. With UNIQUE, the database itself refuses the second one.
Consequences: Check-in can move to its own database later without changing its table. The downside is that the database won't stop a fake ticket code from being saved, so the check-in code always has to ask the tickets part with `validate_ticket(code, event_id)` first.
