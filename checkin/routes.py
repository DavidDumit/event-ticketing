"""Door volunteer pages for the Check-in domain. Business logic lives in checkin/service.py."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from checkin import service
from db import get_db
from tickets import service as tickets_service

bp = Blueprint("checkin", __name__)

# What the volunteer sees when check_in() raises InvalidTicket(reason)
INVALID_MESSAGES = {
    "cancelled": "Ticket cancelled: do not let in.",
    "wrong_event": "This ticket is for a different event.",
    "unknown": "Unknown ticket code.",
}


def _event_or_404(event_id):
    # Read-only lookup of the event (name, sold count) from the Tickets domain,
    # used for the page heading, the 404 and the report's tickets_sold.
    event = tickets_service.get_event(get_db(), event_id)
    if event is None:
        abort(404)
    return event


@bp.route("/events/<int:event_id>/door", methods=["GET", "POST"])
def door(event_id):
    event = _event_or_404(event_id)
    if request.method == "GET":
        stats = service.attendance(get_db(), event_id, event["sold"])
        return render_template("checkin/door.html", event=event, stats=stats)

    code = request.form.get("code", "")
    if not code.strip():
        flash("Type a ticket code.", "error")
        return redirect(url_for("checkin.door", event_id=event_id))

    # The ONLY place the check-in logic reaches into the Tickets domain. In
    # Assignment 2 this lambda becomes an HTTP call to the tickets service.
    validate = lambda code, event_id: tickets_service.validate_ticket(get_db(), code, event_id)

    try:
        service.check_in(get_db(), code, event_id, validate)
    except service.InvalidTicket as e:
        flash(INVALID_MESSAGES.get(e.reason, "This ticket is not valid."), "error")
    except service.AlreadyCheckedIn as e:
        flash(f"Already checked in at {e.checked_in_at[11:16]}", "error")  # '...T20:03:00Z' -> '20:03'
    else:
        flash("Welcome! Ticket checked in", "success")
    # Back to the empty form (autofocused) for the next person; refreshing won't resubmit
    return redirect(url_for("checkin.door", event_id=event_id))


@bp.route("/events/<int:event_id>/report")
def report(event_id):
    event = _event_or_404(event_id)
    conn = get_db()
    return render_template(
        "checkin/report.html",
        event=event,
        stats=service.attendance(conn, event_id, event["sold"]),
        slots=service.arrivals_by_slot(conn, event_id, minutes=15),
    )
