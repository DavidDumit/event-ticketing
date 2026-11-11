"""Tickets service: events and tickets as a JSON API.

Start with:  python app.py
Config comes only from environment variables (see README).
"""
import logging
import os
import time

from flask import Flask, g, jsonify, request

import db
from tickets import service

log = logging.getLogger("tickets")

# Business-rule refusals and the HTTP status each one maps to
ERROR_STATUS = {
    service.EventNotFound: 404,
    service.TicketNotFound: 404,
    service.SalesClosed: 409,
    service.SoldOut: 409,
    service.TicketLimitReached: 409,
    service.TicketAlreadyCancelled: 409,
}


def create_app():
    app = Flask(__name__)
    data_dir = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
    app.config["DB_PATH"] = os.path.join(data_dir, "tickets.db")
    app.config["VERSION"] = os.environ.get("GIT_SHA", "dev")
    app.config["UI_ORIGIN"] = os.environ.get("UI_ORIGIN", "http://localhost:8080")

    db.init_db(app.config["DB_PATH"])
    app.teardown_appcontext(db.close_db)

    @app.before_request
    def start_timer():
        g.start = time.perf_counter()

    @app.after_request
    def log_and_cors(response):
        # One log line per request: method, path, status, duration
        ms = (time.perf_counter() - g.get("start", time.perf_counter())) * 1000
        log.info("%s %s %s %.1fms", request.method, request.path, response.status_code, ms)
        # Only the UI's origin may call this service from a browser
        response.headers["Access-Control-Allow-Origin"] = app.config["UI_ORIGIN"]
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @app.errorhandler(service.TicketError)
    def ticket_error(e):
        return jsonify(error=type(e).__name__, detail=str(e)), ERROR_STATUS.get(type(e), 409)

    @app.get("/health")
    def health():
        """200 if this service can read and write its own database, 503 otherwise."""
        try:
            conn = db.get_connection(app.config["DB_PATH"])
            conn.execute("SELECT COUNT(*) FROM events").fetchone()
            conn.execute("BEGIN IMMEDIATE")  # takes the write lock: proves we can write
            conn.rollback()
            conn.close()
            return jsonify(status="ok", db="ok", version=app.config["VERSION"])
        except Exception:
            return jsonify(status="error", db="unavailable", version=app.config["VERSION"]), 503

    @app.get("/events")
    def list_events():
        return jsonify(service.list_events(db.get_db()))

    @app.post("/events")
    def create_event():
        body = request.get_json(silent=True) or {}
        name = str(body.get("name", "")).strip()
        venue = str(body.get("venue", "")).strip()
        capacity = body.get("capacity")
        if not name or not venue or not isinstance(capacity, int) or capacity <= 0:
            return jsonify(error="ValidationError",
                           detail="name, venue and a whole-number capacity > 0 are required"), 400
        try:
            event_id = service.create_event(db.get_db(), name, venue, body.get("starts_at", ""), capacity)
        except (ValueError, TypeError):
            return jsonify(error="ValidationError", detail="starts_at must be an ISO-8601 time"), 400
        return jsonify(id=event_id), 201

    @app.get("/events/<int:event_id>")
    def get_event(event_id):
        event = service.get_event(db.get_db(), event_id)
        if event is None:
            raise service.EventNotFound(event_id)
        return jsonify(event)

    @app.get("/events/<int:event_id>/tickets")
    def list_tickets(event_id):
        return jsonify(service.list_tickets(db.get_db(), event_id))

    @app.post("/events/<int:event_id>/tickets")
    def sell_ticket(event_id):
        body = request.get_json(silent=True) or {}
        name = str(body.get("holder_name", "")).strip()
        email = str(body.get("holder_email", "")).strip()
        if not name or not email:
            return jsonify(error="ValidationError", detail="holder_name and holder_email are required"), 400
        code = service.issue_ticket(db.get_db(), event_id, name, email)
        return jsonify(code=code), 201

    @app.post("/tickets/<code>/cancel")
    def cancel_ticket(code):
        service.cancel_ticket(db.get_db(), code)
        return jsonify(code=code, status="cancelled")

    @app.get("/tickets/<code>/validate")
    def validate_ticket(code):
        """Called by the check-in service across the seam."""
        event_id = request.args.get("event_id", type=int)
        if event_id is None:
            return jsonify(error="ValidationError", detail="event_id query parameter is required"), 400
        return jsonify(status=service.validate_ticket(db.get_db(), code, event_id))

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    port = int(os.environ.get("PORT", "8000"))
    create_app().run(host="0.0.0.0", port=port)
