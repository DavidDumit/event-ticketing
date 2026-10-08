"""Organiser pages for the Tickets domain. Only calls tickets.service: no SQL here."""
from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from db import get_db
from tickets import service

bp = Blueprint("tickets", __name__)

# What the organiser sees when the service refuses something
ERROR_MESSAGES = {
    service.SoldOut: "Sold out: this event has no seats left.",
    service.SalesClosed: "Sales closed: this event has already started.",
    service.TicketLimitReached: (
        f"This email already has {service.MAX_TICKETS_PER_EMAIL} tickets for this event."
    ),
    service.TicketNotFound: "That ticket does not exist.",
    service.TicketAlreadyCancelled: "That ticket was already cancelled.",
}


@bp.app_template_filter("when")
def format_when(iso_text):
    """'2026-12-01T20:00:00Z' -> '2026-12-01 20:00 UTC' for display."""
    return iso_text[:16].replace("T", " ") + " UTC"


@bp.route("/")
def index():
    return render_template("tickets/index.html", events=service.list_events(get_db()))


@bp.route("/events/new", methods=["GET", "POST"])
def new_event():
    form = request.form
    if request.method == "GET":
        return render_template("tickets/new_event.html", form=form)

    errors, starts_at, capacity = _check_event_form(form)
    if errors:
        for error in errors:
            flash(error, "error")
        # Show the form again with what was typed, so nothing has to be re-entered
        return render_template("tickets/new_event.html", form=form), 400

    event_id = service.create_event(
        get_db(), form["name"].strip(), form["venue"].strip(), starts_at, capacity
    )
    flash("Event created.", "success")
    return redirect(url_for("tickets.event_detail", event_id=event_id))


@bp.route("/events/<int:event_id>")
def event_detail(event_id):
    conn = get_db()
    event = service.get_event(conn, event_id)
    if event is None:
        abort(404)
    return render_template(
        "tickets/event.html", event=event, tickets=service.list_tickets(conn, event_id)
    )


@bp.route("/events/<int:event_id>/tickets", methods=["POST"])
def sell_ticket(event_id):
    name = request.form.get("holder_name", "").strip()
    email = request.form.get("holder_email", "").strip()
    if not name or not email:
        flash("Holder name and email are both required.", "error")
        return redirect(url_for("tickets.event_detail", event_id=event_id))

    try:
        code = service.issue_ticket(get_db(), event_id, name, email)
    except service.EventNotFound:
        abort(404)
    except service.TicketError as e:
        flash(ERROR_MESSAGES.get(type(e), "The ticket could not be issued."), "error")
    else:
        flash(f"Ticket sold to {name}. Ticket code: {code}", "success")
    return redirect(url_for("tickets.event_detail", event_id=event_id))


@bp.route("/tickets/<code>/cancel", methods=["POST"])
def cancel_ticket(code):
    conn = get_db()
    ticket = service.get_ticket(conn, code)
    try:
        service.cancel_ticket(conn, code)
    except service.TicketNotFound as e:
        flash(ERROR_MESSAGES[type(e)], "error")
        return redirect(url_for("tickets.index"))
    except service.TicketAlreadyCancelled as e:
        flash(ERROR_MESSAGES[type(e)], "error")
        return redirect(url_for("tickets.event_detail", event_id=ticket["event_id"]))
    flash(f"Ticket {code} cancelled. Its seat is free again.", "success")
    return redirect(url_for("tickets.event_detail", event_id=ticket["event_id"]))


def _check_event_form(form):
    """Check the create-event form. Returns (errors, starts_at as ISO text, capacity as int)."""
    errors = []
    if not form.get("name", "").strip():
        errors.append("Name is required.")
    if not form.get("venue", "").strip():
        errors.append("Venue is required.")

    # <input type="datetime-local"> sends '2026-12-01T20:00' with no timezone: treat it as UTC
    starts_at = None
    try:
        local = datetime.fromisoformat(form.get("starts_at", ""))
        starts_at = local.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        errors.append("Start time is required.")

    capacity = None
    try:
        capacity = int(form.get("capacity", "").strip())
    except ValueError:
        pass
    if capacity is None or capacity <= 0:
        errors.append("Capacity must be a whole number greater than 0.")

    return errors, starts_at, capacity
