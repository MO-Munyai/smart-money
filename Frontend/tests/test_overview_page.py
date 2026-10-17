from streamlit.testing.v1 import AppTest

from tests.conftest import FakeResponse, page_path, unreachable

PROFILE = {
    "ticker": "AAPL", "name": "Apple Inc.", "type": "Stock", "exchange": "NasdaqGS",
    "currency": "USD", "summary": "Designs phones.", "website": None,
    "details": {}, "registered": False,
}


def run_overview(ticker=None):
    at = AppTest.from_file(page_path("pages/Instrument_Overview.py"), default_timeout=15)
    if ticker is not None:
        at.query_params["ticker"] = ticker
    at.run()
    return at


def test_no_ticker_shows_guidance_and_makes_no_backend_call(backend):
    at = run_overview()
    assert not at.exception
    assert any("No instrument selected" in i.value for i in at.info)
    assert backend.calls == []


def test_blank_ticker_is_treated_as_missing(backend):
    at = run_overview("   ")
    assert any("No instrument selected" in i.value for i in at.info)
    assert backend.calls == []


def test_loads_overview_for_ticker_in_url(backend):
    backend.set("GET", "/instruments/AAPL/overview", FakeResponse(200, PROFILE))
    at = run_overview("AAPL")
    assert not at.exception
    assert len(backend.calls_to("GET", "/instruments/AAPL/overview")) == 1
    assert at.header[0].value == "Apple Inc."
    assert at.caption[0].value == "AAPL · Stock · NasdaqGS · USD"


def test_ticker_is_trimmed(backend):
    backend.set("GET", "/instruments/AAPL/overview", FakeResponse(200, PROFILE))
    run_overview("  AAPL ")
    assert len(backend.calls_to("GET", "/instruments/AAPL/overview")) == 1


def test_special_characters_in_ticker_are_url_encoded(backend):
    backend.set("GET", "/instruments/%5EGSPC/overview",
                FakeResponse(200, {**PROFILE, "ticker": "^GSPC", "name": "S&P 500"}))
    at = run_overview("^GSPC")
    assert not at.exception
    assert at.header[0].value == "S&P 500"


def test_unregistered_instrument_is_flagged(backend):
    backend.set("GET", "/instruments/AAPL/overview", FakeResponse(200, PROFILE))
    at = run_overview("AAPL")
    assert any("Not in your registry" in i.value for i in at.info)


def test_registered_instrument_is_flagged(backend):
    backend.set("GET", "/instruments/AAPL/overview",
                FakeResponse(200, {**PROFILE, "registered": True}))
    at = run_overview("AAPL")
    assert any("In your registry" in s.value for s in at.success)


def test_caption_skips_missing_parts(backend):
    backend.set("GET", "/instruments/^GSPC/overview".replace("^", "%5E"),
                FakeResponse(200, {**PROFILE, "ticker": "^GSPC", "exchange": None, "currency": None}))
    at = run_overview("^GSPC")
    assert at.caption[0].value == "^GSPC · Stock"


def test_invalid_ticker_shows_not_found_warning(backend):
    backend.set("GET", "/instruments/ZZZZ/overview", FakeResponse(404, {"detail": "Ticker not found"}))
    at = run_overview("ZZZZ")
    assert not at.exception
    assert any("No instrument found for 'ZZZZ'" in w.value for w in at.warning)


def test_rate_limit_shows_try_again_warning_not_not_found(backend):
    backend.set("GET", "/instruments/AAPL/overview",
                FakeResponse(503, {"detail": "Yahoo Finance is rate-limiting requests right now - try again shortly"}))
    at = run_overview("AAPL")
    assert any("rate-limiting" in w.value for w in at.warning)
    assert not any("No instrument found" in w.value for w in at.warning)


def test_other_error_status_shows_detail(backend):
    backend.set("GET", "/instruments/AAPL/overview", FakeResponse(500, text="kaboom", json_error=True))
    at = run_overview("AAPL")
    assert any("kaboom" in e.value for e in at.error)


def test_backend_unreachable_shows_error_not_crash(backend):
    backend.set("GET", "/instruments/AAPL/overview", unreachable())
    at = run_overview("AAPL")
    assert not at.exception
    assert any("Could not reach backend" in e.value for e in at.error)


def test_unreadable_json_shows_error(backend):
    backend.set("GET", "/instruments/AAPL/overview", FakeResponse(200, json_error=True))
    at = run_overview("AAPL")
    assert not at.exception
    assert any("unreadable" in e.value for e in at.error)
