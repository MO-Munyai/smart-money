import pandas as pd
import pytest
from yfinance.exceptions import YFRateLimitError

import services.market as market


class FakeTicker:
    def __init__(self, history_df=None, info=None):
        self._history_df = history_df if history_df is not None else pd.DataFrame()
        self.info = info or {}

    def history(self, period=None, interval=None):
        return self._history_df


def make_multi_df(data_dict):
    """Mimics yf.download(group_by='ticker')'s MultiIndex(ticker, field) column shape."""
    return pd.concat({ticker: pd.DataFrame(fields) for ticker, fields in data_dict.items()}, axis=1)


# --- get_live_price_detail / get_live_price ---

def test_get_live_price_detail_happy_path(monkeypatch):
    df = pd.DataFrame({"Close": [721.69]})
    monkeypatch.setattr(market.yf, "Ticker", lambda t: FakeTicker(df, {"currency": "ZAR"}))

    detail = market.get_live_price_detail("NPN.JO")

    assert detail["zar_price"] == 721.69
    assert detail["currency"] == "ZAR"


def test_get_live_price_detail_empty_history_returns_none(monkeypatch):
    monkeypatch.setattr(market.yf, "Ticker", lambda t: FakeTicker(pd.DataFrame(), {}))
    assert market.get_live_price_detail("FAKE") is None


def test_get_live_price_detail_nan_price_returns_none(monkeypatch):
    df = pd.DataFrame({"Close": [float("nan")]})
    monkeypatch.setattr(market.yf, "Ticker", lambda t: FakeTicker(df, {}))
    assert market.get_live_price_detail("FAKE") is None


def test_get_live_price_detail_records_rate_limit_hit(monkeypatch):
    class RaisingTicker:
        def history(self, period=None, interval=None):
            raise YFRateLimitError()

    monkeypatch.setattr(market.yf, "Ticker", lambda t: RaisingTicker())
    before = market.get_rate_limit_state()["hits"]

    result = market.get_live_price_detail("AAPL")

    assert result is None
    assert market.get_rate_limit_state()["hits"] == before + 1


def test_get_live_price_is_a_thin_wrapper_around_detail(monkeypatch):
    df = pd.DataFrame({"Close": [100.0]})
    monkeypatch.setattr(market.yf, "Ticker", lambda t: FakeTicker(df, {"currency": "ZAR"}))
    assert market.get_live_price("X") == 100.0


def test_get_live_price_none_when_detail_none(monkeypatch):
    monkeypatch.setattr(market.yf, "Ticker", lambda t: FakeTicker(pd.DataFrame(), {}))
    assert market.get_live_price("X") is None


# --- get_live_prices (batch NaN handling - 5.8) ---

def test_get_live_prices_drops_nan_and_uses_last_real_value(monkeypatch):
    df = make_multi_df({
        "AAPL": {"Close": [150.0, float("nan")]},  # still-forming bar for a market-hours asset
        "BTC-USD": {"Close": [50000.0, 50500.0]},  # 24/7 asset, has a real "today" value
    })
    monkeypatch.setattr(market.yf, "download", lambda *a, **kw: df)
    monkeypatch.setattr(market.yf, "Ticker", lambda t: FakeTicker(info={"currency": "ZAR"}))

    prices = market.get_live_prices(["AAPL", "BTC-USD"])

    assert prices["AAPL"] == 150.0
    assert prices["BTC-USD"] == 50500.0


def test_get_live_prices_all_nan_is_none(monkeypatch):
    df = make_multi_df({"DEAD": {"Close": [float("nan"), float("nan")]}})
    monkeypatch.setattr(market.yf, "download", lambda *a, **kw: df)
    monkeypatch.setattr(market.yf, "Ticker", lambda t: FakeTicker(info={}))

    assert market.get_live_prices(["DEAD"])["DEAD"] is None


def test_get_live_prices_ticker_absent_from_batch_has_no_key(monkeypatch):
    """
    Documents current behavior: a ticker that never appears in the batch
    download's columns at all gets no entry in the returned dict (not even
    None) - the only reason this is safe today is that /instruments reads
    it via prices.get(ticker), which returns None for a missing key anyway.
    """
    df = make_multi_df({"AAPL": {"Close": [150.0]}})
    monkeypatch.setattr(market.yf, "download", lambda *a, **kw: df)
    monkeypatch.setattr(market.yf, "Ticker", lambda t: FakeTicker(info={"currency": "ZAR"}))

    prices = market.get_live_prices(["AAPL", "GHOST"])

    assert "GHOST" not in prices
    assert prices["AAPL"] == 150.0


def test_get_live_prices_batch_rate_limit_marks_all_none(monkeypatch):
    def raise_rl(*a, **kw):
        raise YFRateLimitError()

    monkeypatch.setattr(market.yf, "download", raise_rl)
    before = market.get_rate_limit_state()["hits"]

    prices = market.get_live_prices(["AAPL", "MSFT"])

    assert prices == {"AAPL": None, "MSFT": None}
    assert market.get_rate_limit_state()["hits"] == before + 1


# --- get_price_history ---

def test_get_price_history_skips_nan_bars_and_normalizes(monkeypatch):
    idx = pd.to_datetime(["2026-01-01", "2026-01-02"])
    df = pd.DataFrame({
        "Open": [100.0, float("nan")],  # a non-trading-day bar for this ticker
        "High": [110.0, 120.0],
        "Low": [90.0, 95.0],
        "Close": [105.0, 115.0],
        "Volume": [1000.0, 2000.0],
    }, index=idx)
    monkeypatch.setattr(market.yf, "Ticker", lambda t: FakeTicker(df, {"currency": "ZAR"}))

    history = market.get_price_history("X", period="1mo", interval="1d")

    assert len(history) == 1
    assert history[0]["close"] == 105.0
    assert history[0]["volume"] == 1000.0


def test_get_price_history_empty_returns_empty_list(monkeypatch):
    monkeypatch.setattr(market.yf, "Ticker", lambda t: FakeTicker(pd.DataFrame(), {}))
    assert market.get_price_history("X") == []


# --- fetch_asset_metadata (5.10 invalid-ticker fix) ---

def test_fetch_asset_metadata_valid_ticker_maps_fields(monkeypatch):
    info = {
        "shortName": "Apple Inc.", "sector": "Technology", "industry": "Consumer Electronics",
        "country": "United States", "marketCap": 3_000_000_000_000, "trailingPE": 30.5,
        "beta": 1.2, "returnOnEquity": 1.4875, "dividendYield": 0.35,
    }
    monkeypatch.setattr(market.yf, "Ticker", lambda t: FakeTicker(info=info))

    meta = market.fetch_asset_metadata("AAPL")

    assert meta["name"] == "Apple Inc."
    assert meta["roe"] == pytest.approx(148.75)  # scaled to match dividend_yield's units
    assert meta["dividend_yield"] == 0.35


def test_fetch_asset_metadata_degenerate_dict_is_invalid(monkeypatch):
    """Yahoo's real invalid-ticker response: a non-empty but useless dict."""
    monkeypatch.setattr(market.yf, "Ticker", lambda t: FakeTicker(info={"trailingPegRatio": None}))
    assert market.fetch_asset_metadata("ZZZZINVALID") is None


def test_fetch_asset_metadata_empty_dict_is_invalid(monkeypatch):
    monkeypatch.setattr(market.yf, "Ticker", lambda t: FakeTicker(info={}))
    assert market.fetch_asset_metadata("ZZZZINVALID") is None


def test_fetch_asset_metadata_rate_limit_records_hit(monkeypatch):
    class RaisingTicker:
        @property
        def info(self):
            raise YFRateLimitError()

    monkeypatch.setattr(market.yf, "Ticker", lambda t: RaisingTicker())
    before = market.get_rate_limit_state()["hits"]

    assert market.fetch_asset_metadata("AAPL") is None
    assert market.get_rate_limit_state()["hits"] == before + 1


# --- get_market_overview caching (6.2) ---

@pytest.fixture(autouse=True)
def reset_overview_cache():
    market._overview_cache["data"] = None
    market._overview_cache["fetched_at"] = None
    yield
    market._overview_cache["data"] = None
    market._overview_cache["fetched_at"] = None


def _fake_batch_result():
    return {
        ticker: {"ticker": ticker, "name": "x", "native_price": 1, "currency": "USD", "fx_rate": None, "zar_price": 1}
        for ticker in market._curated_ticker_index()
    }


def test_get_market_overview_caches_within_ttl(monkeypatch):
    call_count = {"n": 0}

    def fake_batch():
        call_count["n"] += 1
        return _fake_batch_result()

    monkeypatch.setattr(market, "_fetch_curated_batch", fake_batch)

    first = market.get_market_overview()
    second = market.get_market_overview()

    assert call_count["n"] == 1
    assert first == second


def test_get_market_overview_force_bypasses_cache(monkeypatch):
    call_count = {"n": 0}

    def fake_batch():
        call_count["n"] += 1
        return _fake_batch_result()

    monkeypatch.setattr(market, "_fetch_curated_batch", fake_batch)

    market.get_market_overview()
    market.get_market_overview(force=True)

    assert call_count["n"] == 2


# --- rate limit state ---

def test_get_rate_limit_state_returns_a_copy_not_the_live_dict():
    state = market.get_rate_limit_state()
    state["hits"] = -999
    assert market.get_rate_limit_state()["hits"] != -999


# --- fetch_overview_profile (7.1.2) ---

STOCK_INFO = {
    "quoteType": "EQUITY", "longName": "Apple Inc.", "shortName": "Apple",
    "fullExchangeName": "NasdaqGS", "exchange": "NMS", "currency": "USD",
    "longBusinessSummary": "Designs phones.", "website": "https://apple.com",
    "sector": "Technology", "industry": "Consumer Electronics",
    "fullTimeEmployees": 164000, "address1": "One Apple Park Way",
    "city": "Cupertino", "state": "CA", "zip": "95014", "country": "United States",
    "phone": "1 408 996 1010", "irWebsite": "https://investor.apple.com",
    "marketCap": 3_000_000_000_000,
    "companyOfficers": [{"name": "Tim Cook", "title": "CEO", "age": 63}],
}


def patch_info(monkeypatch, info):
    monkeypatch.setattr(market.yf, "Ticker", lambda t: FakeTicker(info=info))


def test_overview_stock_maps_company_details(monkeypatch):
    patch_info(monkeypatch, STOCK_INFO)

    p = market.fetch_overview_profile("aapl")

    assert p["ticker"] == "AAPL"
    assert p["name"] == "Apple Inc."
    assert p["type"] == "Stock"
    assert p["exchange"] == "NasdaqGS"
    assert p["summary"] == "Designs phones."
    assert p["website"] == "https://apple.com"
    assert p["details"]["employees"] == 164000
    assert p["details"]["city"] == "Cupertino"
    assert p["details"]["officers"] == [{"name": "Tim Cook", "title": "CEO"}]
    assert "fund_family" not in p["details"]


def test_overview_stock_missing_optional_fields_are_none(monkeypatch):
    """e.g. NPN.JO: no state, no irWebsite."""
    info = {k: v for k, v in STOCK_INFO.items() if k not in ("state", "irWebsite")}
    patch_info(monkeypatch, info)

    d = market.fetch_overview_profile("NPN.JO")["details"]

    assert d["state"] is None
    assert d["ir_website"] is None
    assert d["sector"] == "Technology"


def test_overview_stock_officers_are_capped_and_nameless_ones_dropped(monkeypatch):
    officers = [{"name": f"Person {i}", "title": "VP"} for i in range(15)]
    officers.insert(0, {"title": "No name"})
    patch_info(monkeypatch, {**STOCK_INFO, "companyOfficers": officers})

    got = market.fetch_overview_profile("AAPL")["details"]["officers"]

    assert len(got) == market._MAX_OVERVIEW_OFFICERS
    assert all(o["name"] for o in got)
    assert got[0]["name"] == "Person 0"


def test_overview_etf_maps_fund_details_and_converts_inception_date(monkeypatch):
    patch_info(monkeypatch, {
        "quoteType": "ETF", "longName": "SPDR S&P 500", "currency": "USD",
        "longBusinessSummary": "Tracks the S&P 500.", "fundFamily": "State Street",
        "category": "Large Blend", "legalType": "Exchange Traded Fund",
        "fundInceptionDate": 727660800, "totalAssets": 5e11, "navPrice": 600.1,
    })

    p = market.fetch_overview_profile("SPY")

    assert p["type"] == "ETF"
    assert p["summary"] == "Tracks the S&P 500."
    assert p["website"] is None
    assert p["details"] == {
        "fund_family": "State Street", "category": "Large Blend",
        "legal_type": "Exchange Traded Fund", "inception_date": "1993-01-22",
        "total_assets": 5e11, "nav_price": 600.1,
    }


def test_overview_crypto_uses_description_field_for_summary(monkeypatch):
    patch_info(monkeypatch, {
        "quoteType": "CRYPTOCURRENCY", "shortName": "Bitcoin USD", "currency": "USD",
        "description": "Bitcoin is a cryptocurrency.", "website": "https://bitcoin.org/",
        "circulatingSupply": 19_800_000, "marketCap": 2e12, "startDate": 1278979200,
    })

    p = market.fetch_overview_profile("BTC-USD")

    assert p["type"] == "Crypto"
    assert p["summary"] == "Bitcoin is a cryptocurrency."
    assert p["details"] == {
        "circulating_supply": 19_800_000, "market_cap": 2e12, "launch_date": "2010-07-13",
    }


def test_overview_index_has_no_summary_and_empty_details(monkeypatch):
    patch_info(monkeypatch, {
        "quoteType": "INDEX", "longName": "S&P 500", "currency": "USD", "exchange": "SNP",
    })

    p = market.fetch_overview_profile("^GSPC")

    assert p["type"] == "Index"
    assert p["summary"] is None
    assert p["website"] is None
    assert p["details"] == {}
    assert p["exchange"] == "SNP"


def test_overview_unrecognised_quote_type_gets_no_type_and_empty_details(monkeypatch):
    patch_info(monkeypatch, {"quoteType": "MUTUALFUND", "longName": "Some Fund"})

    p = market.fetch_overview_profile("VFIAX")

    assert p["type"] is None
    assert p["details"] == {}


def test_overview_name_falls_back_to_short_name_then_ticker(monkeypatch):
    patch_info(monkeypatch, {"quoteType": "EQUITY", "shortName": "Short"})
    assert market.fetch_overview_profile("x")["name"] == "Short"

    patch_info(monkeypatch, {"quoteType": "EQUITY", "regularMarketPrice": 1.0})
    assert market.fetch_overview_profile("x")["name"] == "X"


def test_overview_degenerate_dict_is_invalid(monkeypatch):
    patch_info(monkeypatch, {"trailingPegRatio": None})
    assert market.fetch_overview_profile("ZZZZINVALID") is None


def test_overview_empty_dict_is_invalid(monkeypatch):
    patch_info(monkeypatch, {})
    assert market.fetch_overview_profile("ZZZZINVALID") is None


def test_overview_rate_limit_records_hit_and_reraises(monkeypatch):
    class RaisingTicker:
        @property
        def info(self):
            raise YFRateLimitError()

    monkeypatch.setattr(market.yf, "Ticker", lambda t: RaisingTicker())
    before = market.get_rate_limit_state()["hits"]

    with pytest.raises(YFRateLimitError):
        market.fetch_overview_profile("AAPL")

    assert market.get_rate_limit_state()["hits"] == before + 1


def test_unix_to_iso_date_rejects_non_numbers_and_garbage():
    assert market._unix_to_iso_date(None) is None
    assert market._unix_to_iso_date("1278979200") is None
    assert market._unix_to_iso_date(True) is None
    assert market._unix_to_iso_date(10**20) is None
    assert market._unix_to_iso_date(0) == "1970-01-01"


def test_overview_quote_type_map_matches_search_module():
    from services import search
    assert market._OVERVIEW_QUOTE_TYPES == search.QUOTE_TYPE_MAP
