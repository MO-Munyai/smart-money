from streamlit.testing.v1 import AppTest

from tests.conftest import FakeResponse, page_path, unreachable


def overview_payload():
    ok = {"ticker": "AAPL", "name": "Apple", "native_price": 200.0,
          "currency": "USD", "fx_rate": 18.5, "zar_price": 3700.0}
    zar = {"ticker": "NPN.JO", "name": "Naspers", "native_price": 3000.0,
           "currency": "ZAR", "fx_rate": None, "zar_price": 3000.0}
    bad = {"ticker": "XXX", "name": "Broken", "error": "no price"}
    return {"by_type": {"stocks": [ok, zar, bad], "etfs": [ok]},
            "by_country": {"USA": [ok], "South Africa": [zar]}}


def run_markets():
    at = AppTest.from_file(page_path("pages/Markets.py"), default_timeout=15)
    at.run()
    return at


def test_auto_loads_and_renders_tabs(backend):
    backend.set("GET", "/markets/overview", FakeResponse(200, overview_payload()))
    at = run_markets()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Stocks", "Etfs", "USA", "South Africa"]
    assert len(backend.calls_to("GET", "/markets/overview")) == 1


def test_entries_to_df_formats_rows(backend):
    backend.set("GET", "/markets/overview", FakeResponse(200, overview_payload()))
    at = run_markets()
    df = at.dataframe[0].value
    rows = {r["Ticker"]: r for _, r in df.iterrows()}
    assert rows["AAPL"]["ZAR Price"] == "R 3,700.00"
    assert rows["AAPL"]["FX Rate (-> ZAR)"] == "18.5"
    assert rows["NPN.JO"]["FX Rate (-> ZAR)"] == "1:1 (ZAR-equivalent)"
    assert rows["XXX"]["ZAR Price"] == "no price"
    assert rows["XXX"]["Native Price"] == "N/A"


def test_refresh_now_passes_force_to_backend(backend):
    backend.set("GET", "/markets/overview", FakeResponse(200, overview_payload()))
    at = run_markets()
    at.button[0].click().run()
    assert not at.exception
    assert backend.calls_to("GET", "/markets/overview")[-1][2] == {"force": "true"}


def test_second_visit_within_ttl_uses_streamlit_cache(backend):
    backend.set("GET", "/markets/overview", FakeResponse(200, overview_payload()))
    run_markets()
    run_markets()
    assert len(backend.calls_to("GET", "/markets/overview")) == 1


def test_backend_unreachable_shows_error(backend):
    backend.set("GET", "/markets/overview", unreachable())
    at = run_markets()
    assert not at.exception
    assert any("Could not reach backend" in e.value for e in at.error)


def test_backend_error_shows_detail(backend):
    backend.set("GET", "/markets/overview", FakeResponse(500, {"detail": "yahoo down"}))
    at = run_markets()
    assert any("yahoo down" in e.value for e in at.error)


def test_unreadable_json_shows_error(backend):
    backend.set("GET", "/markets/overview", FakeResponse(200, json_error=True))
    at = run_markets()
    assert any("unreadable" in e.value for e in at.error)
