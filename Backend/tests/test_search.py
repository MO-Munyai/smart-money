import pytest
from yfinance.exceptions import YFRateLimitError

import services.search as search


class FakeSearch:
    def __init__(self, quotes):
        self.quotes = quotes


def test_quote_type_filters_out_of_scope_types(monkeypatch):
    """FUTURE/OPTION/MUTUALFUND etc. aren't in QUOTE_TYPE_MAP - should be dropped, not crash."""
    quotes = [
        {"symbol": "AAPL", "shortname": "Apple Inc.", "quoteType": "EQUITY", "exchange": "NMS", "exchDisp": "NASDAQ"},
        {"symbol": "ES=F", "shortname": "E-Mini S&P 500", "quoteType": "FUTURE", "exchange": "CME", "exchDisp": "CME"},
    ]
    monkeypatch.setattr(search.yf, "Search", lambda q, max_results=None: FakeSearch(quotes))

    results = search.search_instruments("sp500")

    assert len(results) == 1
    assert results[0]["ticker"] == "AAPL"
    assert results[0]["type"] == "Stock"


def test_type_filter_narrows_results(monkeypatch):
    quotes = [
        {"symbol": "BTC-USD", "shortname": "Bitcoin USD", "quoteType": "CRYPTOCURRENCY", "exchange": "CCC", "exchDisp": "CCC"},
        {"symbol": "IBIT", "shortname": "iShares Bitcoin Trust ETF", "quoteType": "ETF", "exchange": "NGM", "exchDisp": "NASDAQ"},
    ]
    monkeypatch.setattr(search.yf, "Search", lambda q, max_results=None: FakeSearch(quotes))

    results = search.search_instruments("bitcoin", type_filter="Crypto")

    assert len(results) == 1
    assert results[0]["ticker"] == "BTC-USD"


def test_country_filter_resolves_known_exchange(monkeypatch):
    quotes = [
        {"symbol": "SHP.JO", "longname": "Shoprite Holdings Ltd", "quoteType": "EQUITY",
         "exchange": "JNB", "exchDisp": "Johannesburg Stock Exchange"},
        {"symbol": "SRGHY", "longname": "Shoprite Holdings Ltd", "quoteType": "EQUITY",
         "exchange": "PNK", "exchDisp": "OTC Markets"},
    ]
    monkeypatch.setattr(search.yf, "Search", lambda q, max_results=None: FakeSearch(quotes))

    results = search.search_instruments("shoprite", country_filter="South Africa")

    assert len(results) == 1
    assert results[0]["ticker"] == "SHP.JO"
    assert results[0]["country"] == "South Africa"


def test_unmapped_exchange_falls_back_to_its_own_display_name_not_literal_other(monkeypatch):
    """
    EXCHANGE_COUNTRY_MAP is intentionally incomplete. An unmapped exchange
    resolves to Yahoo's own exchDisp string (e.g. "Kuala Lumpur Stock
    Exchange"), NOT the literal "Other" bucket - "Other" only fires when
    exchDisp is itself missing. This means filtering by country="Other" in
    the UI will rarely match anything in practice, since most results carry
    their own real exchange name instead. Documented here, not silently
    "fixed", since changing it is a product call (lose the specific
    exchange name vs. make the "Other" filter actually catch things).
    """
    quotes = [
        {"symbol": "XYZ.KL", "shortname": "Some Malaysian-adjacent Thing", "quoteType": "EQUITY",
         "exchange": "ZZZ_UNMAPPED", "exchDisp": "Some Obscure Exchange"},
    ]
    monkeypatch.setattr(search.yf, "Search", lambda q, max_results=None: FakeSearch(quotes))

    results = search.search_instruments("thing")

    assert results[0]["country"] == "Some Obscure Exchange"
    assert results[0]["country"] != "Other"


def test_missing_exchange_and_display_name_falls_back_to_other(monkeypatch):
    quotes = [
        {"symbol": "WEIRD", "shortname": "Weird Thing", "quoteType": "EQUITY",
         "exchange": None, "exchDisp": None},
    ]
    monkeypatch.setattr(search.yf, "Search", lambda q, max_results=None: FakeSearch(quotes))

    results = search.search_instruments("weird")

    assert results[0]["country"] == "Other"


def test_name_prefers_longname_over_shortname(monkeypatch):
    quotes = [{"symbol": "AAPL", "shortname": "Apple", "longname": "Apple Inc.",
               "quoteType": "EQUITY", "exchange": "NMS", "exchDisp": "NASDAQ"}]
    monkeypatch.setattr(search.yf, "Search", lambda q, max_results=None: FakeSearch(quotes))

    results = search.search_instruments("apple")

    assert results[0]["name"] == "Apple Inc."


def test_empty_query_short_circuits_without_calling_yahoo(monkeypatch):
    def fail_if_called(*a, **kw):
        raise AssertionError("yf.Search should not be called for an empty query")
    monkeypatch.setattr(search.yf, "Search", fail_if_called)

    assert search.search_instruments("") == []
    assert search.search_instruments("   ") == []


def test_rate_limit_returns_empty_and_records_hit(monkeypatch):
    def raise_rl(q, max_results=None):
        raise YFRateLimitError()
    monkeypatch.setattr(search.yf, "Search", raise_rl)

    from services.market import get_rate_limit_state
    hits_before = get_rate_limit_state()["hits"]

    results = search.search_instruments("anything")

    assert results == []
    assert get_rate_limit_state()["hits"] == hits_before + 1


def test_limit_truncates_after_filtering(monkeypatch):
    quotes = [
        {"symbol": f"T{i}", "shortname": f"Thing {i}", "quoteType": "EQUITY",
         "exchange": "NMS", "exchDisp": "NASDAQ"}
        for i in range(10)
    ]
    monkeypatch.setattr(search.yf, "Search", lambda q, max_results=None: FakeSearch(quotes))

    results = search.search_instruments("thing", limit=3)

    assert len(results) == 3


def test_get_known_types_matches_quote_type_map_values():
    assert search.get_known_types() == ["Stock", "ETF", "Crypto", "Index"]


def test_get_known_countries_includes_other_bucket():
    countries = search.get_known_countries()
    assert "Other" in countries
    assert "South Africa" in countries
    assert countries == sorted(countries[:-1]) + ["Other"]
