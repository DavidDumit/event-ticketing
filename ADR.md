# Architecture Decision Records

## 1. Backend language and framework: Python + Flask
Date: 2026-10-05
Status: Decided
Context: I needed to pick a language and framework for a small web app with two parts (tickets and check-in), one SQLite database and a few simple pages. It has to start with one command, and I have to be able to explain all of the code myself in the comprehension check.
Decision: I went with Python and Flask, because Python is the language I'm most comfortable with. I use Python's built-in `sqlite3` module to talk to the database and Jinja templates for the pages.
Alternatives considered: Django, but it comes with a lot of things I don't need (an admin panel, its own way of handling the database, a fixed project structure), and the assignment says picking it without a reason counts as poor judgement. FastAPI, but it's mainly good for building APIs and fast async apps, and my app is just a few HTML pages with not much traffic. I also looked at SQLAlchemy for the database, but writing plain SQL means I can see exactly what's happening and explain it more easily.
Consequences: The project stays small and easy to follow, with only a few packages. The downside is that I have to write the SQL myself, and if I change the database structure later there's no automatic tool to update it.

## 2. Keeping tickets and check-in separate so they can be split later
Date: 2026-10-09
Status: Decided
Context: My app has two parts: tickets (organisers create events and sell tickets) and check-in (volunteers let people in at the door). For now they run in one app, but in Assignment 2 they need to become separate services, so I have to decide now where the line between them goes and what is allowed to cross it.
Decision: Each part has its own folder (`tickets/` and `checkin/`) and its own tables. Check-in never imports any tickets code and never reads the tickets or events tables. The only thing that crosses the line is one question, `validate(code, event_id)`, which is passed into `check_in()` and answers "valid", "cancelled", "wrong_event" or "unknown". Things like the number of tickets sold are also passed in instead of looked up.
Alternatives considered: Letting check-in import the tickets service or query the tickets table directly. That would be quicker to write, but then check-in would depend on how tickets stores its data, and splitting them later would mean rewriting check-in. I also thought about one shared module for both parts, but then there would be no clear line to cut along.
Consequences: In Assignment 2, the only change in check-in is that `validate` becomes a web request to the tickets service instead of a normal function call. It also means I can test check-in on its own with a fake validate function. The downside is a bit of repeated code (the small date helpers exist in both parts) and the app has to pass the validate function in every time.

## 3. No foreign key between the check-in and tickets tables
Date: 2026-10-07
Status: Decided
Context: The tickets part of the app owns the `events` and `tickets` tables, and the check-in part owns the `check_ins` table. Check-in needs to know which ticket was scanned, but in Assignment 2 the two parts should be able to become separate services, each with its own database.
Decision: Inside the tickets part, `tickets.event_id` is a normal foreign key to `events`, since both tables belong together. But `check_ins` just stores the ticket code and event id as plain values, with no link to the tickets table. I also made `ticket_code` UNIQUE in `check_ins`, so the same ticket can't be checked in twice.
Alternatives considered: Linking `check_ins` to `tickets` with a foreign key. I didn't do this because it would tie the two parts together in the database, and splitting them later would mean redesigning the tables. I also thought about stopping double entry with an "already used?" check in Python before saving, but if two volunteers scan the same ticket at the exact same moment, both checks could pass. With UNIQUE, the database itself refuses the second one.
Consequences: Check-in can move to its own database later without changing its table. The downside is that the database won't stop a fake ticket code from being saved, so the check-in code always has to ask the tickets part with `validate_ticket(code, event_id)` first.

## 4. Testing approach: business rules first, then the main user flows
Date: 2026-10-10
Status: Decided
Context: The assignment asks for at least 70% coverage on the core business logic of both parts. I had limited time, so I had to decide what was most important to test and what could stay thinner.
Decision: Most of my tests are on the business rules in `tickets/service.py` and `checkin/service.py`, because that's where mistakes would really hurt (selling more tickets than seats, letting someone in twice). Each of those tests gets a fresh database in memory and passes the time in itself, so results never depend on the clock. Check-in is tested with a fake validate function, so it's tested without the tickets part. After that I added page tests with Flask's test client for the main flows, like selling a ticket and then checking it in at the door. I run them with `pytest --cov=tickets --cov=checkin --cov-report=term-missing`, which gives about 96% overall.
Alternatives considered: Testing mostly through the pages. That would cover more code per test, but when something fails it's harder to see which rule broke, and every rule would need a full page request. I also thought about browser tests (like Selenium), but that's a lot of setup for a few simple HTML pages.
Consequences: The rules are tested well and the tests run fast. Thinner parts: some rare error paths in the pages (like a missing name when selling), how the pages look, two people buying the last ticket at the exact same moment (I only checked that once by hand), and the Docker container, which is checked by the provided `run.sh` instead of pytest.

## 5. Not building QR code scanning at the door
Date: 2026-10-12
Status: Decided
Context: At the door, volunteers need to check tickets quickly. The obvious way would be to show a QR code on each ticket and scan it with a phone camera, and I had it in my original plan.
Decision: I didn't build QR codes. Volunteers type the ticket code into a big input box on the door page instead.
Alternatives considered: Scanning QR codes with the phone camera. That needs JavaScript in the browser, a camera permission, a scanning library and testing on different phones, which is a lot of extra work and risk for this assignment. Only showing a QR code on the ticket would also need an extra package, and it doesn't help without a scanner. Typing the code still tests all the important logic: is the ticket valid, and has it already been used.
Consequences: Checking people in is slower, and typing mistakes are possible (they show up as "Unknown ticket code", so nobody gets in by mistake). QR could be added later without changing the database or the check-in logic, because the QR code would just contain the same ticket code.

