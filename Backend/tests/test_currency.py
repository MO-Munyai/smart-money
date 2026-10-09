import services.currency as currency


def test_same_currency_short_circuits_to_rate_one():
    assert currency.get_forex_rate("ZAR", "ZAR") == 1.0


def test_zar_native_needs_no_forex_lookup(monkeypatch):
    def fail_if_called(*a, **kw):
        raise AssertionError("get_forex_rate should not be called for ZAR-denominated prices")
    monkeypatch.setattr(currency, "get_forex_rate", fail_if_called)

    breakdown = currency.get_price_breakdown("SOL.JO", 100.0, "ZAR")

    assert breakdown == {
        "native_price": 100.0, "currency": "ZAR", "fx_rate": None, "zar_price": 100.0
    }


def test_minor_unit_zac_scales_to_major_and_skips_forex(monkeypatch):
    """ZAc (JSE cents) is ZAR's own minor unit - no currency conversion needed, just /100."""
    def fail_if_called(*a, **kw):
        raise AssertionError("ZAc->ZAR should never need a forex lookup")
    monkeypatch.setattr(currency, "get_forex_rate", fail_if_called)

    breakdown = currency.get_price_breakdown("NPN.JO", 72169.0, "ZAc")

    assert breakdown["native_price"] == 721.69
    assert breakdown["currency"] == "ZAR"
    assert breakdown["fx_rate"] is None
    assert breakdown["zar_price"] == 721.69


def test_minor_unit_gbp_pence_scales_then_still_converts(monkeypatch):
    """GBp (LSE pence) needs the /100 unit fix AND a real GBP->ZAR forex lookup."""
    monkeypatch.setattr(currency, "get_forex_rate", lambda frm, to="ZAR": 23.5)

    breakdown = currency.get_price_breakdown("AZN.L", 11876.0, "GBp")

    assert breakdown["native_price"] == 118.76
    assert breakdown["currency"] == "GBP"
    assert breakdown["fx_rate"] == 23.5
    assert breakdown["zar_price"] == 118.76 * 23.5


def test_gbx_is_treated_the_same_as_gbp(monkeypatch):
    monkeypatch.setattr(currency, "get_forex_rate", lambda frm, to="ZAR": 23.5)
    breakdown = currency.get_price_breakdown("X.L", 10000.0, "GBX")
    assert breakdown["currency"] == "GBP"
    assert breakdown["native_price"] == 100.0


def test_foreign_currency_applies_fx_rate(monkeypatch):
    monkeypatch.setattr(currency, "get_forex_rate", lambda frm, to="ZAR": 18.5)

    breakdown = currency.get_price_breakdown("AAPL", 200.0, "USD")

    assert breakdown["native_price"] == 200.0
    assert breakdown["currency"] == "USD"
    assert breakdown["fx_rate"] == 18.5
    assert breakdown["zar_price"] == 3700.0


def test_fx_lookup_failure_falls_back_to_native_price_unconverted(monkeypatch):
    """
    If Yahoo has no rate for a pair, get_forex_rate returns None - the
    breakdown should reflect that honestly (fx_rate None) rather than
    silently pretending native == ZAR.
    """
    monkeypatch.setattr(currency, "get_forex_rate", lambda frm, to="ZAR": None)

    breakdown = currency.get_price_breakdown("WEIRD", 50.0, "XYZ")

    assert breakdown["fx_rate"] is None
    assert breakdown["zar_price"] == 50.0  # unconverted, not silently wrong


def test_normalize_price_returns_just_the_zar_figure(monkeypatch):
    monkeypatch.setattr(currency, "get_forex_rate", lambda frm, to="ZAR": 18.5)
    assert currency.normalize_price("AAPL", 200.0, "USD") == 3700.0


def test_get_forex_rate_returns_none_on_empty_history(monkeypatch):
    class FakeTicker:
        def history(self, period):
            import pandas as pd
            return pd.DataFrame()

    monkeypatch.setattr(currency.yf, "Ticker", lambda ticker: FakeTicker())
    currency.FOREX_CACHE.clear()

    assert currency.get_forex_rate("XXX", "ZAR") is None


def test_get_forex_rate_caches_successful_lookup(monkeypatch):
    import pandas as pd
    call_count = {"n": 0}

    class FakeTicker:
        def history(self, period):
            call_count["n"] += 1
            return pd.DataFrame({"Close": [19.25]})

    monkeypatch.setattr(currency.yf, "Ticker", lambda ticker: FakeTicker())
    currency.FOREX_CACHE.clear()

    first = currency.get_forex_rate("USD", "ZAR")
    second = currency.get_forex_rate("USD", "ZAR")

    assert first == 19.25
    assert second == 19.25
    assert call_count["n"] == 1  # second call served from FOREX_CACHE
