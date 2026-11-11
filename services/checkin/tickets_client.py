"""HTTP client for the tickets service: the only way check-in reaches tickets.

The base URL comes from TICKETS_URL (e.g. http://tickets:8000 in compose) and
every call has a timeout (TICKETS_TIMEOUT_S), so a slow or stopped tickets
service never hangs a check-in request.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class TicketsUnavailable(Exception):
    """The tickets service could not be reached or answered with an error."""


def _base_url():
    return os.environ.get("TICKETS_URL", "http://localhost:8001").rstrip("/")


def _timeout():
    return float(os.environ.get("TICKETS_TIMEOUT_S", "2"))


def _get(path):
    """GET a JSON document from tickets. Returns None on 404."""
    try:
        with urllib.request.urlopen(_base_url() + path, timeout=_timeout()) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise TicketsUnavailable(f"tickets answered {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise TicketsUnavailable(str(e)) from e


def validate(code, event_id):
    """'valid', 'cancelled', 'wrong_event' or 'unknown' for a scanned code."""
    query = urllib.parse.urlencode({"event_id": event_id})
    data = _get(f"/tickets/{urllib.parse.quote(code, safe='')}/validate?{query}")
    if data is None:
        return "unknown"
    return data["status"]


def get_event(event_id):
    """The event as a dict (with 'sold'), or None if it doesn't exist."""
    return _get(f"/events/{event_id}")
