import main
from tests.conftest import seed_instrument


# --- POST /instruments ---

def test_register_new_instrument_succeeds(client, monkeypatch):
    monkeypatch.setattr(main, "get_live_price", lambda ticker: 123.45)

    r = client.post("/instruments", json={"ticker": "aapl", "type": "Stock"})

    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["type"] == "Stock"


def test_register_duplicate_returns_400(client, db, monkeypatch):
    seed_instrument(db, "AAPL")
    monkeypatch.setattr(main, "get_live_price", lambda ticker: 123.45)

    r = client.post("/instruments", json={"ticker": "AAPL", "type": "Stock"})

    assert r.status_code == 400


def test_register_unresolvable_ticker_returns_404(client, monkeypatch):
    monkeypatch.setattr(main, "get_live_price", lambda ticker: None)

    r = client.post("/instruments", json={"ticker": "ZZZZINVALID", "type": "Stock"})

    assert r.status_code == 404


def test_register_invalid_type_enum_returns_422(client):
    r = client.post("/instruments", json={"ticker": "AAPL", "type": "NotARealType"})
    assert r.status_code == 422


# --- GET /instruments ---

def test_list_instruments_empty_registry(client):
    r = client.get("/instruments")
    assert r.status_code == 200
    assert r.json() == []


def test_list_instruments_includes_live_price(client, db, monkeypatch):
    seed_instrument(db, "AAPL", "Stock")
    seed_instrument(db, "BTC-USD", "Crypto")
    monkeypatch.setattr(main, "get_live_prices", lambda tickers: {"AAPL": 5000.0, "BTC-USD": 1_300_000.0})

    r = client.get("/instruments")

    assert r.status_code == 200
    body = {row["ticker"]: row for row in r.json()}
    assert body["AAPL"]["live_price"] == 5000.0
    assert body["BTC-USD"]["live_price"] == 1_300_000.0


def test_list_instruments_missing_price_key_is_none(client, db, monkeypatch):
    """Covers get_live_prices' documented gap: a ticker absent from its result dict."""
    seed_instrument(db, "GHOST", "Stock")
    monkeypatch.setattr(main, "get_live_prices", lambda tickers: {})

    r = client.get("/instruments")

    assert r.json()[0]["live_price"] is None


# --- DELETE /instruments/{ticker} ---

def test_remove_registered_instrument(client, db):
    seed_instrument(db, "AAPL")
    r = client.delete("/instruments/AAPL")
    assert r.status_code == 200
    assert client.get("/instruments").json() == []


def test_remove_unknown_instrument_returns_404(client):
    r = client.delete("/instruments/NOPE")
    assert r.status_code == 404


# --- GET /instruments/{ticker} ---

def test_get_detail_for_registered_instrument(client, db, monkeypatch):
    seed_instrument(db, "AAPL", "Stock")
    monkeypatch.setattr(main, "fetch_asset_metadata", lambda ticker: {
        "ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology", "pe_ratio": 30.0,
    })
    monkeypatch.setattr(main, "get_live_price", lambda ticker: 5000.0)

    r = client.get("/instruments/AAPL")

    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Apple Inc."
    assert body["live_price"] == 5000.0
    assert body["type"] == "Stock"


def test_get_detail_for_unregistered_instrument_returns_404(client):
    r = client.get("/instruments/AAPL")
    assert r.status_code == 404


# --- GET /instruments/{ticker}/history ---

def test_get_history_for_registered_instrument(client, db, monkeypatch):
    seed_instrument(db, "AAPL", "Stock")
    fake_history = [{"date": "2026-01-01T00:00:00", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100}]
    monkeypatch.setattr(main, "get_price_history", lambda ticker, period, interval: fake_history)

    r = client.get("/instruments/AAPL/history", params={"period": "1mo", "interval": "1d"})

    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["history"] == fake_history


def test_get_history_for_unregistered_instrument_returns_404(client):
    r = client.get("/instruments/AAPL/history")
    assert r.status_code == 404


# --- GET /instruments/compare ---

def test_compare_two_valid_tickers(client, monkeypatch):
    monkeypatch.setattr(main, "fetch_asset_metadata", lambda ticker: {"ticker": ticker, "name": ticker})
    monkeypatch.setattr(main, "get_live_price", lambda ticker: 100.0)

    r = client.get("/instruments/compare", params={"tickers": "AAPL,MSFT"})

    assert r.status_code == 200
    assert len(r.json()["instruments"]) == 2


def test_compare_drops_invalid_ticker_but_keeps_valid_ones(client, monkeypatch):
    def fake_metadata(ticker):
        return None if ticker == "ZZZZINVALID" else {"ticker": ticker, "name": ticker}
    monkeypatch.setattr(main, "fetch_asset_metadata", fake_metadata)
    monkeypatch.setattr(main, "get_live_price", lambda ticker: 100.0)

    r = client.get("/instruments/compare", params={"tickers": "AAPL,ZZZZINVALID"})

    assert r.status_code == 200
    assert len(r.json()["instruments"]) == 1


def test_compare_all_invalid_returns_404(client, monkeypatch):
    monkeypatch.setattr(main, "fetch_asset_metadata", lambda ticker: None)

    r = client.get("/instruments/compare", params={"tickers": "ZZZZINVALID,ALSOFAKE"})

    assert r.status_code == 404


def test_compare_fewer_than_two_returns_400(client):
    r = client.get("/instruments/compare", params={"tickers": "AAPL"})
    assert r.status_code == 400


# --- Route ordering regressions (compare/search/search/meta must not be
#     swallowed by GET /instruments/{ticker}) ---

def test_compare_route_not_shadowed_by_ticker_route(client, monkeypatch):
    monkeypatch.setattr(main, "fetch_asset_metadata", lambda ticker: {"ticker": ticker, "name": ticker})
    monkeypatch.setattr(main, "get_live_price", lambda ticker: 1.0)

    r = client.get("/instruments/compare", params={"tickers": "AAPL,MSFT"})

    assert r.status_code == 200
    assert "instruments" in r.json()  # not the {ticker} detail shape (would 404/different body)


def test_search_route_not_shadowed_by_ticker_route(client, monkeypatch):
    monkeypatch.setattr(main, "search_instruments", lambda q, type_filter=None, country_filter=None: [])

    r = client.get("/instruments/search", params={"q": "whatever"})

    assert r.status_code == 200
    assert r.json() == {"results": []}


def test_search_meta_route_not_shadowed_by_ticker_route(client, monkeypatch):
    monkeypatch.setattr(main, "get_known_types", lambda: ["Stock"])
    monkeypatch.setattr(main, "get_known_countries", lambda: ["Other"])

    r = client.get("/instruments/search/meta")

    assert r.status_code == 200
    assert r.json() == {"types": ["Stock"], "countries": ["Other"]}


# --- GET /instruments/search ---

def test_search_endpoint_passes_filters_through(client, monkeypatch):
    captured = {}

    def fake_search(q, type_filter=None, country_filter=None):
        captured["q"] = q
        captured["type_filter"] = type_filter
        captured["country_filter"] = country_filter
        return [{"ticker": "SHP.JO", "name": "Shoprite Holdings Ltd", "type": "Stock",
                  "exchange": "Johannesburg Stock Exchange", "country": "South Africa"}]

    monkeypatch.setattr(main, "search_instruments", fake_search)

    r = client.get("/instruments/search", params={"q": "shoprite", "type": "Stock", "country": "South Africa"})

    assert r.status_code == 200
    assert captured == {"q": "shoprite", "type_filter": "Stock", "country_filter": "South Africa"}
    assert r.json()["results"][0]["ticker"] == "SHP.JO"
