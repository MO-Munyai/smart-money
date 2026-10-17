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


# --- profile rendering (7.1.5) ---

STOCK_PROFILE = {
    "ticker": "AAPL", "name": "Apple Inc.", "type": "Stock", "exchange": "NasdaqGS",
    "currency": "USD", "summary": "Designs phones and computers.",
    "website": "https://apple.com", "registered": True,
    "details": {
        "sector": "Technology", "industry": "Consumer Electronics", "employees": 164000,
        "market_cap": 3e12, "address": "One Apple Park Way", "city": "Cupertino",
        "state": "CA", "zip": "95014", "country": "United States", "phone": "1 408 996 1010",
        "ir_website": "https://investor.apple.com",
        "officers": [{"name": "Tim Cook", "title": "CEO"}],
    },
}


def load(backend, profile, ticker="AAPL"):
    backend.set("GET", f"/instruments/{ticker}/overview", FakeResponse(200, profile))
    return run_overview(ticker)


def subheaders(at):
    return [s.value for s in at.subheader]


def all_markdown(at):
    return " ".join(m.value for m in at.markdown)


def test_stock_profile_renders_every_section(backend):
    at = load(backend, STOCK_PROFILE)
    assert not at.exception
    assert subheaders(at) == ["About", "Key facts", "Links", "Key officers"]
    text = all_markdown(at)
    assert "Designs phones and computers." in text
    assert "**Sector**  \nTechnology" in text
    assert "**Employees**  \n164,000" in text
    assert "**Market cap**  \n3.00T" in text
    assert "[Website](https://apple.com)" in text
    assert "[Investor relations](https://investor.apple.com)" in text
    officers = at.dataframe[0].value
    assert list(officers.columns) == ["Title", "Name"]
    assert list(officers["Name"]) == ["Tim Cook"]
    assert list(officers["Title"]) == ["CEO"]


def test_sparse_stock_hides_missing_fields_and_shows_no_na(backend):
    """NPN.JO-style: no website, IR site, state, phone or employees."""
    sparse = {**STOCK_PROFILE, "website": None, "details": {
        "sector": "Consumer Cyclical", "city": "Cape Town", "country": "South Africa",
        "state": None, "phone": None, "employees": None, "ir_website": None, "officers": [],
    }}
    at = load(backend, sparse)
    text = all_markdown(at)
    assert "Phone" not in text
    assert "Employees" not in text
    assert "Links" not in subheaders(at)
    assert "Key officers" not in subheaders(at)
    assert "N/A" not in text
    assert "**Headquarters**  \nCape Town, South Africa" in text


def test_short_summary_has_no_expander(backend):
    at = load(backend, STOCK_PROFILE)
    assert len(at.expander) == 0


def test_long_summary_is_split_with_the_rest_in_an_expander(backend):
    long_text = "A fairly long sentence about the business. " * 40
    at = load(backend, {**STOCK_PROFILE, "summary": long_text})
    assert len(at.expander) == 1
    assert at.expander[0].label == "Read the full description"


def test_missing_summary_hides_about_section(backend):
    at = load(backend, {**STOCK_PROFILE, "summary": None})
    assert "About" not in subheaders(at)
    assert "Key facts" in subheaders(at)


def test_etf_profile_shows_fund_facts(backend):
    etf = {"ticker": "SPY", "name": "SPDR S&P 500", "type": "ETF", "exchange": "NYSEArca",
           "currency": "USD", "summary": "Tracks the index.", "website": None, "registered": False,
           "details": {"fund_family": "State Street", "category": "Large Blend",
                       "legal_type": None, "inception_date": "1993-01-22",
                       "total_assets": 8.09e11, "nav_price": 771.8012}}
    at = load(backend, etf, "SPY")
    text = all_markdown(at)
    assert "**Fund family**  \nState Street" in text
    assert "**Inception**  \n22 Jan 1993" in text
    assert "**NAV price**  \n771.80" in text
    assert "Legal type" not in text
    assert "Links" not in subheaders(at)


def test_crypto_profile_shows_supply_and_launch(backend):
    crypto = {"ticker": "BTC-USD", "name": "Bitcoin USD", "type": "Crypto", "exchange": "CCC",
              "currency": "USD", "summary": "A cryptocurrency.", "website": "https://bitcoin.org/",
              "registered": True,
              "details": {"circulating_supply": 20_098_844, "market_cap": 1.64e12,
                          "launch_date": "2010-07-13"}}
    at = load(backend, crypto, "BTC-USD")
    text = all_markdown(at)
    assert "**Circulating supply**  \n20.10M" in text
    assert "**Launched**  \n13 Jul 2010" in text
    assert "[Website](https://bitcoin.org/)" in text


def test_index_shows_fallback_message_and_no_sections(backend):
    index = {"ticker": "^GSPC", "name": "S&P 500", "type": "Index", "exchange": "SNP",
             "currency": "USD", "summary": None, "website": None, "details": {},
             "registered": False}
    backend.set("GET", "/instruments/%5EGSPC/overview", FakeResponse(200, index))
    at = run_overview("^GSPC")
    assert not at.exception
    assert any("indices" in i.value for i in at.info)
    assert subheaders(at) == []


def test_unrecognised_type_with_nothing_shows_generic_fallback(backend):
    bare = {"ticker": "X", "name": "Thing", "type": None, "exchange": None, "currency": None,
            "summary": None, "website": None, "details": {}, "registered": False}
    at = load(backend, bare, "X")
    assert any("this instrument" in i.value for i in at.info)
