import requests

import api_client


class FakeResponse:
    def __init__(self, json_data=None, text="", json_error=False):
        self._json_data = json_data
        self.text = text
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("not JSON")
        return self._json_data


# --- api_request ---

def test_api_request_defaults_timeout_to_15(monkeypatch):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(api_client.requests, "request", fake_request)

    r, err = api_client.api_request("GET", "http://x/instruments")

    assert err is None
    assert captured["timeout"] == 15


def test_api_request_honors_explicit_timeout_override(monkeypatch):
    """
    Regression test for the real bug caught before 5.6 shipped: the old
    hardcoded timeout=15 collided with a caller passing timeout= explicitly,
    raising TypeError. setdefault() must not clobber an explicit override.
    """
    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(api_client.requests, "request", fake_request)

    r, err = api_client.api_request("GET", "http://x/markets/overview", timeout=45)

    assert err is None
    assert captured["timeout"] == 45


def test_api_request_unreachable_backend_degrades_to_message_not_raise(monkeypatch):
    def fake_request(method, url, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(api_client.requests, "request", fake_request)

    r, err = api_client.api_request("GET", "http://x/instruments")

    assert r is None
    assert "Could not reach backend" in err


def test_api_request_passes_through_method_params_json(monkeypatch):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(api_client.requests, "request", fake_request)

    api_client.api_request("POST", "http://x/instruments", json={"ticker": "AAPL"})

    assert captured["method"] == "POST"
    assert captured["url"] == "http://x/instruments"
    assert captured["json"] == {"ticker": "AAPL"}


# --- error_detail ---

def test_error_detail_extracts_detail_field():
    response = FakeResponse(json_data={"detail": "Instrument not found"})
    assert api_client.error_detail(response, "fallback") == "Instrument not found"


def test_error_detail_falls_back_when_no_detail_key():
    response = FakeResponse(json_data={"something_else": "x"})
    assert api_client.error_detail(response, "fallback") == "fallback"


def test_error_detail_falls_back_to_response_text_on_non_json():
    """FastAPI's default handler for an unhandled 500 returns plain text, not JSON."""
    response = FakeResponse(json_error=True, text="Internal Server Error")
    assert api_client.error_detail(response, "fallback") == "Internal Server Error"


def test_error_detail_uses_fallback_when_text_is_also_empty():
    response = FakeResponse(json_error=True, text="")
    assert api_client.error_detail(response, "fallback") == "fallback"


# --- safe_json ---

def test_safe_json_returns_parsed_value():
    response = FakeResponse(json_data=[{"ticker": "AAPL"}])
    assert api_client.safe_json(response) == [{"ticker": "AAPL"}]


def test_safe_json_returns_fallback_on_invalid_json():
    response = FakeResponse(json_error=True)
    assert api_client.safe_json(response) is None
    assert api_client.safe_json(response, fallback="default") == "default"
