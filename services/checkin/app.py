"""Check-in service: door check-ins and attendance reports as a JSON API.

Start with:  python app.py
Config comes only from environment variables (see README).
"""
import logging
import os
import time

from flask import Flask, g, jsonify, request

import db
import tickets_client
from checkin import service

log = logging.getLogger("checkin")


def create_app():
    app = Flask(__name__)
    data_dir = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
    app.config["DB_PATH"] = os.path.join(data_dir, "checkin.db")
    app.config["VERSION"] = os.environ.get("GIT_SHA", "dev")
    app.config["UI_ORIGIN"] = os.environ.get("UI_ORIGIN", "http://localhost:8080")

    db.init_db(app.config["DB_PATH"])
    app.teardown_appcontext(db.close_db)

    @app.before_request
    def start_timer():
        g.start = time.perf_counter()

    @app.after_request
    def log_and_cors(response):
        ms = (time.perf_counter() - g.get("start", time.perf_counter())) * 1000
        log.info("%s %s %s %.1fms", request.method, request.path, response.status_code, ms)
        response.headers["Access-Control-Allow-Origin"] = app.config["UI_ORIGIN"]
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @app.errorhandler(tickets_client.TicketsUnavailable)
    def tickets_down(e):
        # Designed failure: a clear 503 instead of a stack trace or a hung request
        log.warning("tickets service unavailable: %s", e)
        return jsonify(error="TicketsUnavailable",
                       detail="The tickets service is unavailable; try again shortly."), 503

    @app.get("/health")
    def health():
        """Reflects only this service's own database, not the tickets service."""
        try:
            conn = db.get_connection(app.config["DB_PATH"])
            conn.execute("SELECT COUNT(*) FROM check_ins").fetchone()
            conn.execute("BEGIN IMMEDIATE")
            conn.rollback()
            conn.close()
            return jsonify(status="ok", db="ok", version=app.config["VERSION"])
        except Exception:
            return jsonify(status="error", db="unavailable", version=app.config["VERSION"]), 503

    @app.post("/events/<int:event_id>/checkins")
    def check_in(event_id):
        """The cross-seam flow: validating the code needs the tickets service."""
        body = request.get_json(silent=True) or {}
        code = str(body.get("code", "")).strip()
        if not code:
            return jsonify(error="ValidationError", detail="code is required"), 400
        if tickets_client.get_event(event_id) is None:
            return jsonify(error="EventNotFound", detail=str(event_id)), 404
        try:
            service.check_in(db.get_db(), code, event_id, tickets_client.validate)
        except service.InvalidTicket as e:
            return jsonify(error="InvalidTicket", reason=e.reason), 409
        except service.AlreadyCheckedIn as e:
            return jsonify(error="AlreadyCheckedIn", checked_in_at=e.checked_in_at), 409
        return jsonify(code=code, status="checked_in"), 201

    @app.get("/events/<int:event_id>/report")
    def report(event_id):
        conn = db.get_db()
        slots = [{"slot_start": s, "count": c} for s, c in service.arrivals_by_slot(conn, event_id)]
        try:
            event = tickets_client.get_event(event_id)
        except tickets_client.TicketsUnavailable:
            # Degraded: our own numbers still work, tickets sold is unknown
            checked_in = service.attendance(conn, event_id, 0)["checked_in"]
            return jsonify(event_id=event_id, checked_in=checked_in, tickets_sold=None,
                           no_shows=None, rate=None, arrivals=slots,
                           notice="Tickets service unavailable: sales figures not shown.")
        if event is None:
            return jsonify(error="EventNotFound", detail=str(event_id)), 404
        stats = service.attendance(conn, event_id, event["sold"])
        return jsonify(event_id=event_id, tickets_sold=event["sold"], arrivals=slots, **stats)

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    port = int(os.environ.get("PORT", "8000"))
    create_app().run(host="0.0.0.0", port=port)
