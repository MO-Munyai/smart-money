import requests

API_URL = "http://127.0.0.1:8000"


def api_request(method, url, **kwargs):
    """
    Wraps a requests call so a fully unreachable backend (connection refused,
    timeout, DNS failure, etc.) degrades to (None, message) instead of
    crashing the page. Distinct from error_detail() below, which handles the
    separate case of "got a response back, but it was an error".
    """
    try:
        return requests.request(method, url, timeout=15, **kwargs), None
    except requests.exceptions.RequestException as e:
        return None, f"Could not reach backend: {e}"


def error_detail(response, fallback):
    """
    Safely pulls a {"detail": ...} message out of a failed response.
    FastAPI's default handler returns plain text (not JSON) for unhandled
    server errors (e.g. a 500), so response.json() itself can raise - this
    falls back to the raw text, or the given fallback, instead of crashing.
    """
    try:
        return response.json().get("detail", fallback)
    except ValueError:
        return response.text or fallback


def safe_json(response, fallback=None):
    """Parses a response body as JSON, returning fallback instead of raising if it isn't."""
    try:
        return response.json()
    except ValueError:
        return fallback
