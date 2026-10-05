# Architecture Decision Records

## 1. Backend language and framework: Python + Flask
Date: 2026-10-05
Status: Decided
Context: The app is a small server-rendered monolith with two domains, one SQLite database and a few pages for organisers and door volunteers. It has to run as a single process started by one command, and I need to be able to explain every line of it.
Decision: Python with Flask, using the built-in `sqlite3` module instead of an ORM and Jinja templates for the pages.
Alternatives considered: Django: rejected because its ORM, admin and project structure are more than this app needs, and the course grades unnecessary framework weight down. FastAPI: rejected because its main strengths (async, automatic API docs) don't matter for a server-rendered app with low traffic. SQLAlchemy: rejected because plain SQL keeps the schema visible and easy to explain.
Consequences: Fewer dependencies and less magic, so the code is easy to read and test. The cost is writing SQL and request handling by hand, and having no built-in migrations if the schema changes later.
