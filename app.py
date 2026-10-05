"""Entry point for the Event Ticketing app.

Start with:  python app.py
Config comes only from environment variables (see README).
"""
import os

from flask import Flask

import db


def create_app():
    app = Flask(__name__)

    # All config from env vars, with sane defaults (deployment contract §7.3, §7.5, §7.9)
    data_dir = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
    app.config["DB_PATH"] = os.path.join(data_dir, "app.db")

    # Create the data folder and the database on startup: no manual setup step (§7.4)
    db.init_db(app.config["DB_PATH"])

    @app.route("/health")
    def health():
        # Proves the app can actually talk to SQLite, not just that Flask is up
        conn = db.get_connection(app.config["DB_PATH"])
        conn.execute("SELECT 1")
        conn.close()
        return {"status": "ok"}

    @app.route("/")
    def index():
        return "Event Ticketing is running."

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    # 0.0.0.0 so it is reachable from outside a container (§7.2)
    create_app().run(host="0.0.0.0", port=port)
