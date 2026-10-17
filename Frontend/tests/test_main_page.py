from streamlit.testing.v1 import AppTest

from tests.conftest import FakeResponse, page_path, unreachable

REGISTRY = [{"ticker": "AAPL", "type": "Stock", "live_price": 3700.0},
            {"ticker": "BTC-USD", "type": "Crypto", "live_price": 1.2e6}]

DETAIL = {"ticker": "AAPL", "name": "Apple Inc", "type": "Stock", "live_price": 3700.0,
          "pe_ratio": 30.5, "beta": 1.2, "dividend_yield": 0.5, "sector": "Tech",
          "industry": "Hardware", "country": "USA", "market_cap": 3e12, "roe": 1.5,
          "added_at": "2026-10-01"}

BARS = [{"date": "2026-10-01", "open": 1, "high": 2, "low": 0.5, "close": 1.5},
        {"date": "2026-10-02", "open": 1.5, "high": 2.5, "low": 1, "close": 2}]

SEARCH_RESULTS = [{"ticker": "SHP.JO", "name": "Shoprite", "type": "Stock",
                   "exchange": "JSE", "country": "South Africa"}]


def route_defaults(backend, registry=REGISTRY, results=None):
    backend.set("GET", "/instruments/search/meta",
                FakeResponse(200, {"types": ["Stock", "ETF"], "countries": ["USA", "Other"]}))
    backend.set("GET", "/instruments", FakeResponse(200, registry))
    backend.set("GET", "/instruments/AAPL", FakeResponse(200, DETAIL))
    backend.set("GET", "/instruments/AAPL/history", FakeResponse(200, {"history": BARS}))
    backend.set("GET", "/instruments/BTC-USD", FakeResponse(200, {**DETAIL, "ticker": "BTC-USD"}))
    backend.set("GET", "/instruments/BTC-USD/history", FakeResponse(200, {"history": BARS}))
    backend.set("GET", "/instruments/search", FakeResponse(200, {"results": results or []}))


def run_main():
    at = AppTest.from_file(page_path("app.py"), default_timeout=20)
    at.run()
    return at


def button(at, label):
    return [b for b in at.button if b.label == label][0]


# --- registry / detail ---

def test_renders_registry_detail_and_history(backend):
    route_defaults(backend)
    at = run_main()
    assert not at.exception
    assert len(at.dataframe) >= 1
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Live Price (ZAR)"] == "R 3700.00"
    assert metrics["P/E Ratio"] == "30.50"
    assert metrics["Dividend Yield"] == "0.50%"
    assert len(at.get("plotly_chart")) == 1


def test_empty_registry_shows_info(backend):
    route_defaults(backend, registry=[])
    at = run_main()
    assert not at.exception
    assert any("No instruments registered yet" in i.value for i in at.info)


def test_missing_detail_fields_render_na(backend):
    route_defaults(backend)
    backend.set("GET", "/instruments/AAPL", FakeResponse(200, {"ticker": "AAPL", "type": "Stock"}))
    at = run_main()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Live Price (ZAR)"] == "N/A"
    assert metrics["Beta"] == "N/A"


def test_empty_history_shows_info(backend):
    route_defaults(backend)
    backend.set("GET", "/instruments/AAPL/history", FakeResponse(200, {"history": []}))
    at = run_main()
    assert any("No price history" in i.value for i in at.info)


def test_backend_unreachable_degrades_gracefully(backend):
    backend.set("GET", "/instruments/search/meta", unreachable())
    backend.set("GET", "/instruments", unreachable())
    at = run_main()
    assert not at.exception
    assert any("Could not reach backend" in e.value for e in at.error)


def test_registry_error_status_shows_detail(backend):
    route_defaults(backend)
    backend.set("GET", "/instruments", FakeResponse(500, text="db locked", json_error=True))
    at = run_main()
    assert any("db locked" in e.value for e in at.error)


def test_detail_error_shows_detail_message(backend):
    route_defaults(backend)
    backend.set("GET", "/instruments/AAPL", FakeResponse(404, {"detail": "not found"}))
    at = run_main()
    assert any("not found" in e.value for e in at.error)


# --- history controls ---

def test_default_interval_and_period(backend):
    route_defaults(backend)
    at = run_main()
    assert at.selectbox(key="history_interval").value == "1d"
    assert at.selectbox(key="history_period_1d").value == "6mo"
    assert backend.calls_to("GET", "/instruments/AAPL/history")[-1][2] == \
        {"period": "6mo", "interval": "1d"}


def test_switching_interval_restricts_period_options(backend):
    route_defaults(backend)
    at = run_main()
    at.selectbox(key="history_interval").select("1m").run()
    assert not at.exception
    assert at.selectbox(key="history_period_1m").options == ["1d", "5d"]
    assert backend.calls_to("GET", "/instruments/AAPL/history")[-1][2] == \
        {"period": "1d", "interval": "1m"}


# --- compare ---

def test_compare_prompts_until_two_selected(backend):
    route_defaults(backend)
    at = run_main()
    assert any("at least two" in i.value for i in at.info)


def test_compare_two_tickers_calls_backend(backend):
    route_defaults(backend)
    backend.set("GET", "/instruments/compare", FakeResponse(200, {"instruments": [
        {"ticker": "AAPL", "pe_ratio": 30}, {"ticker": "BTC-USD", "pe_ratio": None}]}))
    at = run_main()
    at.multiselect(key="compare_tickers").select("AAPL").select("BTC-USD").run()
    assert not at.exception
    assert backend.calls_to("GET", "/instruments/compare")[-1][2] == {"tickers": "AAPL,BTC-USD"}


def test_compare_error_shows_detail(backend):
    route_defaults(backend)
    backend.set("GET", "/instruments/compare", FakeResponse(404, {"detail": "none valid"}))
    at = run_main()
    at.multiselect(key="compare_tickers").select("AAPL").select("BTC-USD").run()
    assert any("none valid" in e.value for e in at.error)


# --- register form ---

def test_register_blank_ticker_errors_without_calling_backend(backend):
    route_defaults(backend)
    at = run_main()
    button(at, "Register").click().run()
    assert any("Enter a ticker first" in e.value for e in at.error)
    assert backend.calls_to("POST", "/instruments") == []


def test_register_posts_trimmed_ticker_and_type(backend):
    route_defaults(backend)
    backend.set("POST", "/instruments", FakeResponse(200, {"ticker": "MSFT", "type": "ETF"}))
    at = run_main()
    at.text_input[1].set_value("  msft ")
    at.selectbox[2].select("ETF")
    button(at, "Register").click().run()
    assert backend.calls_to("POST", "/instruments")[-1][3] == {"ticker": "msft", "type": "ETF"}
    assert any("MSFT registered" in s.value for s in at.success)


def test_register_failure_shows_backend_detail(backend):
    route_defaults(backend)
    backend.set("POST", "/instruments", FakeResponse(400, {"detail": "already registered"}))
    at = run_main()
    at.text_input[1].set_value("AAPL")
    button(at, "Register").click().run()
    assert any("already registered" in e.value for e in at.error)


# --- remove ---

def test_remove_calls_delete_for_selected_ticker(backend):
    route_defaults(backend)
    backend.set("DELETE", "/instruments/AAPL", FakeResponse(200, {"message": "ok"}))
    at = run_main()
    button(at, "Remove").click().run()
    assert len(backend.calls_to("DELETE", "/instruments/AAPL")) == 1


def test_remove_failure_shows_detail(backend):
    route_defaults(backend)
    backend.set("DELETE", "/instruments/AAPL", FakeResponse(404, {"detail": "gone"}))
    at = run_main()
    button(at, "Remove").click().run()
    assert any("gone" in e.value for e in at.error)


# --- search ---

def test_search_filters_populate_from_meta(backend):
    route_defaults(backend)
    at = run_main()
    assert at.selectbox(key="instrument_search_type").options == ["Any", "Stock", "ETF"]
    assert at.selectbox(key="instrument_search_country").options == ["Any", "USA", "Other"]


def test_search_meta_failure_still_offers_any(backend):
    route_defaults(backend)
    backend.set("GET", "/instruments/search/meta", unreachable())
    at = run_main()
    assert not at.exception
    assert at.selectbox(key="instrument_search_type").options == ["Any"]


def test_blank_search_makes_no_search_call(backend):
    route_defaults(backend)
    run_main()
    assert backend.calls_to("GET", "/instruments/search") == []


def test_search_sends_query_and_filters(backend):
    route_defaults(backend, results=SEARCH_RESULTS)
    at = run_main()
    at.text_input(key="instrument_search_query").set_value("  shoprite ")
    at.selectbox(key="instrument_search_type").select("Stock")
    at.selectbox(key="instrument_search_country").select("USA")
    at.run()
    assert backend.calls_to("GET", "/instruments/search")[-1][2] == \
        {"q": "shoprite", "type": "Stock", "country": "USA"}


def test_search_any_filters_are_omitted(backend):
    route_defaults(backend, results=SEARCH_RESULTS)
    at = run_main()
    at.text_input(key="instrument_search_query").set_value("shoprite").run()
    assert backend.calls_to("GET", "/instruments/search")[-1][2] == {"q": "shoprite"}


def test_search_no_results_shows_info(backend):
    route_defaults(backend, results=[])
    at = run_main()
    at.text_input(key="instrument_search_query").set_value("zzzz").run()
    assert any("No matches" in i.value for i in at.info)


def test_search_error_shows_detail(backend):
    route_defaults(backend)
    backend.set("GET", "/instruments/search", FakeResponse(500, {"detail": "search broke"}))
    at = run_main()
    at.text_input(key="instrument_search_query").set_value("x").run()
    assert any("search broke" in e.value for e in at.error)


def test_search_result_register_button_posts_result(backend):
    route_defaults(backend, results=SEARCH_RESULTS)
    backend.set("POST", "/instruments", FakeResponse(200, {"ticker": "SHP.JO", "type": "Stock"}))
    at = run_main()
    at.text_input(key="instrument_search_query").set_value("shoprite").run()
    at.button(key="register_search_SHP.JO").click().run()
    assert backend.calls_to("POST", "/instruments")[-1][3] == {"ticker": "SHP.JO", "type": "Stock"}


# --- search result Overview button (7.1.6) ---

SHP_OVERVIEW = {"ticker": "SHP.JO", "name": "Shoprite Holdings", "type": "Stock",
                "exchange": "Johannesburg", "currency": "ZAc", "summary": None,
                "website": None, "details": {}, "registered": False}


def test_search_result_has_overview_and_register_buttons(backend):
    route_defaults(backend, results=SEARCH_RESULTS)
    at = run_main()
    at.text_input(key="instrument_search_query").set_value("shoprite").run()
    assert at.button(key="overview_search_SHP.JO").label == "Overview"
    assert at.button(key="register_search_SHP.JO").label == "Register"


def test_search_result_overview_button_opens_overview_page_for_that_ticker(backend):
    route_defaults(backend, results=SEARCH_RESULTS)
    backend.set("GET", "/instruments/SHP.JO/overview", FakeResponse(200, SHP_OVERVIEW))
    at = run_main()
    at.text_input(key="instrument_search_query").set_value("shoprite").run()
    at.button(key="overview_search_SHP.JO").click().run()
    assert not at.exception
    assert at.query_params["ticker"] == ["SHP.JO"]
    assert len(backend.calls_to("GET", "/instruments/SHP.JO/overview")) == 1
    assert at.header[0].value == "Shoprite Holdings"


def test_search_result_overview_button_does_not_register(backend):
    route_defaults(backend, results=SEARCH_RESULTS)
    backend.set("GET", "/instruments/SHP.JO/overview", FakeResponse(200, SHP_OVERVIEW))
    at = run_main()
    at.text_input(key="instrument_search_query").set_value("shoprite").run()
    at.button(key="overview_search_SHP.JO").click().run()
    assert backend.calls_to("POST", "/instruments") == []


def test_each_search_result_gets_its_own_overview_button(backend):
    two = SEARCH_RESULTS + [{"ticker": "NPN.JO", "name": "Naspers", "type": "Stock",
                             "exchange": "JSE", "country": "South Africa"}]
    route_defaults(backend, results=two)
    backend.set("GET", "/instruments/NPN.JO/overview",
                FakeResponse(200, {**SHP_OVERVIEW, "ticker": "NPN.JO", "name": "Naspers"}))
    at = run_main()
    at.text_input(key="instrument_search_query").set_value("jo").run()
    at.button(key="overview_search_NPN.JO").click().run()
    assert at.query_params["ticker"] == ["NPN.JO"]
    assert backend.calls_to("GET", "/instruments/SHP.JO/overview") == []


# --- registry Overview button (7.1.7) ---

def test_registry_selector_is_labelled_for_both_actions(backend):
    route_defaults(backend)
    at = run_main()
    assert at.selectbox(key="registry_ticker").label == "Select instrument"
    assert at.selectbox(key="registry_ticker").options == ["AAPL", "BTC-USD"]
    assert button(at, "Overview") is not None
    assert button(at, "Remove") is not None


def test_registry_overview_button_opens_page_for_the_selected_ticker(backend):
    route_defaults(backend)
    backend.set("GET", "/instruments/AAPL/overview",
                FakeResponse(200, {**SHP_OVERVIEW, "ticker": "AAPL", "name": "Apple Inc.",
                                   "registered": True}))
    at = run_main()
    button(at, "Overview").click().run()
    assert not at.exception
    assert at.query_params["ticker"] == ["AAPL"]
    assert at.header[0].value == "Apple Inc."


def test_registry_overview_button_follows_a_changed_selection(backend):
    route_defaults(backend)
    backend.set("GET", "/instruments/BTC-USD/overview",
                FakeResponse(200, {**SHP_OVERVIEW, "ticker": "BTC-USD", "name": "Bitcoin USD",
                                   "type": "Crypto", "registered": True}))
    at = run_main()
    at.selectbox(key="registry_ticker").select("BTC-USD").run()
    button(at, "Overview").click().run()
    assert at.query_params["ticker"] == ["BTC-USD"]
    assert backend.calls_to("GET", "/instruments/AAPL/overview") == []


def test_registry_overview_button_does_not_delete_anything(backend):
    route_defaults(backend)
    backend.set("GET", "/instruments/AAPL/overview",
                FakeResponse(200, {**SHP_OVERVIEW, "ticker": "AAPL", "registered": True}))
    at = run_main()
    button(at, "Overview").click().run()
    assert backend.calls_to("DELETE", "/instruments/AAPL") == []


def test_remove_still_deletes_the_selected_registry_ticker(backend):
    route_defaults(backend)
    backend.set("DELETE", "/instruments/BTC-USD", FakeResponse(200, {"message": "ok"}))
    at = run_main()
    at.selectbox(key="registry_ticker").select("BTC-USD").run()
    button(at, "Remove").click().run()
    assert len(backend.calls_to("DELETE", "/instruments/BTC-USD")) == 1
