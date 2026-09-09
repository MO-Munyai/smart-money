# services/market.py

import math
from datetime import datetime, timezone
import yfinance as yf
from yfinance.exceptions import YFRateLimitError
from services.currency import normalize_price, get_price_breakdown

# Module-level rate-limit tracking. yfinance is an unofficial scraper around
# Yahoo's endpoints with no published rate-limit headers/dashboard to check
# proactively (see Docs/yfinance-notes.md) - the best we can do is notice
# when it happens and make it distinguishable from "ticker doesn't exist" or
# any other failure, instead of swallowing it as a generic exception.
_rate_limit_state = {"hits": 0, "last_hit_at": None}


def _record_rate_limit_hit(context: str):
    _rate_limit_state["hits"] += 1
    _rate_limit_state["last_hit_at"] = datetime.now(timezone.utc)
    print(
        f"[rate-limit] YFRateLimitError #{_rate_limit_state['hits']} "
        f"in {context} at {_rate_limit_state['last_hit_at'].isoformat()}"
    )


def get_rate_limit_state():
    """Snapshot of rate-limit hits so far - consumed by the /health endpoint."""
    return dict(_rate_limit_state)


def get_live_price_detail(ticker: str):
    """
    Like get_live_price, but returns the full conversion breakdown instead
    of just the final ZAR figure: native price, native currency, the fx
    rate applied (if any), and the ZAR price. Needed for the dual-currency
    market overview (5.6) - get_live_price() previously discarded all of
    this once it converted to ZAR.
    Returns None if the ticker can't be resolved.
    """
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")
        if data.empty:
            return None

        raw_price = float(data["Close"].iloc[-1])
        if math.isnan(raw_price):
            return None

        currency = stock.info.get("currency", "ZAR")
        return get_price_breakdown(ticker, raw_price, currency)
    except YFRateLimitError:
        _record_rate_limit_hit(f"get_live_price_detail[{ticker}]")
        return None
    except Exception:
        return None


def get_live_price(ticker: str):
    """
    Fetches live price for a single ticker with currency normalization.
    """
    detail = get_live_price_detail(ticker)
    return detail["zar_price"] if detail else None


def get_live_prices(tickers: list[str]):
    """
    Batch fetch live prices for multiple tickers.
    Returns a dict: {ticker: normalized_price}
    """
    prices = {}
    try:
        tickers_str = " ".join(tickers)
        data = yf.download(tickers_str, period="1d", group_by="ticker", threads=True)

        for ticker in tickers:
            try:
                if ticker in data.columns.levels[0]:
                    raw_price = float(data[ticker]["Close"].iloc[-1])
                    # yf.download batches tickers against a shared trading-day
                    # index - a ticker whose market was closed that day (e.g.
                    # a public holiday) comes back NaN rather than absent.
                    # NaN isn't JSON-serializable, so it has to become "price
                    # unavailable" (None) instead of silently propagating and
                    # 500ing the response.
                    if math.isnan(raw_price):
                        prices[ticker] = None
                        continue
                    info = yf.Ticker(ticker).info
                    currency = info.get("currency", "ZAR")
                    prices[ticker] = normalize_price(ticker, raw_price, currency)
            except YFRateLimitError:
                _record_rate_limit_hit(f"get_live_prices[{ticker}]")
                prices[ticker] = None
            except Exception:
                prices[ticker] = None
    except YFRateLimitError:
        _record_rate_limit_hit("get_live_prices[batch download]")
        for ticker in tickers:
            prices[ticker] = None
    except Exception as e:
        print(f"Error fetching batch prices: {e}")
        for ticker in tickers:
            prices[ticker] = None

    return prices


def get_price_history(ticker: str, period: str = "6mo", interval: str = "1d"):
    """
    Fetches OHLC price history for a ticker, ZAR-normalized like get_live_price.
    Returns a list of {date, open, high, low, close, volume} dicts, oldest first.
    """
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period=period, interval=interval)
        if data.empty:
            return []

        currency = stock.info.get("currency", "ZAR")
        history = []
        for ts, row in data.iterrows():
            ohlc = [float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])]
            if any(math.isnan(v) for v in ohlc):
                # Non-trading day for this ticker (e.g. a market holiday) -
                # NaN isn't JSON-serializable, so skip the bar rather than
                # let it through.
                continue
            history.append({
                "date": ts.isoformat(),
                "open": normalize_price(ticker, ohlc[0], currency),
                "high": normalize_price(ticker, ohlc[1], currency),
                "low": normalize_price(ticker, ohlc[2], currency),
                "close": normalize_price(ticker, ohlc[3], currency),
                "volume": float(row["Volume"])
            })
        return history
    except YFRateLimitError:
        _record_rate_limit_hit(f"get_price_history[{ticker}]")
        return []
    except Exception as e:
        print(f"Error fetching history for {ticker}: {e}")
        return []


# Curated top-10-per-category instruments for the default market overview
# (5.5/5.6). yfinance has no working screener for ETF/index/crypto categories
# (see Docs/yfinance-notes.md), so all four categories use a fixed list for
# consistency rather than mixing a dynamic screener for stocks with curated
# lists for the rest.
#
# Currency is hardcoded per ticker rather than looked up live: an
# instrument's quote currency essentially never changes, and looking it up
# via .info was the dominant cost of this endpoint - confirmed live, doing
# it for all 40 tickers took ~57s vs ~12s once removed (get_live_price_detail
# still looks currency up live for user-registered instruments, since those
# aren't a fixed list). Verified against real yfinance data on 2026-09-09.
# Price itself is always still fetched live, every request.
CURATED_MARKETS = {
    "stocks": [
        ("AAPL", "USD"), ("MSFT", "USD"), ("GOOGL", "USD"), ("AMZN", "USD"),
        ("NVDA", "USD"), ("META", "USD"), ("TSLA", "USD"), ("BRK-B", "USD"),
        ("JPM", "USD"), ("V", "USD"),
    ],
    "etfs": [
        ("SPY", "USD"), ("QQQ", "USD"), ("VOO", "USD"), ("VTI", "USD"),
        ("IVV", "USD"), ("GLD", "USD"), ("VYM", "USD"), ("SCHD", "USD"),
        ("ARKK", "USD"), ("XLK", "USD"),
    ],
    "indices": [
        ("^GSPC", "USD"), ("^DJI", "USD"), ("^IXIC", "USD"), ("^RUT", "USD"),
        ("^VIX", "USD"), ("^FTSE", "GBP"), ("^N225", "JPY"), ("^GDAXI", "EUR"),
        ("^HSI", "HKD"), ("^STOXX50E", "EUR"),
    ],
    "crypto": [
        ("BTC-USD", "USD"), ("ETH-USD", "USD"), ("SOL-USD", "USD"), ("BNB-USD", "USD"),
        ("XRP-USD", "USD"), ("ADA-USD", "USD"), ("DOGE-USD", "USD"), ("AVAX-USD", "USD"),
        ("DOT-USD", "USD"), ("LINK-USD", "USD"),
    ],
}


def get_market_overview():
    """
    Live price breakdown (native price, currency, fx rate, ZAR price) for
    the curated top-10 per category. Returns
    {category: [{ticker, native_price, currency, fx_rate, zar_price}, ...]},
    with {"ticker": ..., "error": "..."} entries for any ticker that failed.
    """
    overview = {}
    for category, entries in CURATED_MARKETS.items():
        results = []
        for ticker, currency in entries:
            try:
                stock = yf.Ticker(ticker)
                data = stock.history(period="1d")
                if data.empty:
                    results.append({"ticker": ticker, "error": "no data"})
                    continue

                raw_price = float(data["Close"].iloc[-1])
                if math.isnan(raw_price):
                    results.append({"ticker": ticker, "error": "no data"})
                    continue

                breakdown = get_price_breakdown(ticker, raw_price, currency)
                results.append({"ticker": ticker, **breakdown})
            except YFRateLimitError:
                _record_rate_limit_hit(f"get_market_overview[{ticker}]")
                results.append({"ticker": ticker, "error": "rate limited"})
            except Exception as e:
                print(f"Error fetching overview price for {ticker}: {e}")
                results.append({"ticker": ticker, "error": "fetch failed"})
        overview[category] = results
    return overview


def fetch_asset_metadata(ticker: str):
    """
    Fetches fundamental metadata for a given ticker from Yahoo Finance.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        if not info:
            return None

        roe_raw = info.get("returnOnEquity")

        return {
            "ticker": ticker.upper(),
            "name": info.get("shortName") or info.get("longName") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "beta": info.get("beta"),
            # yfinance returns returnOnEquity as a raw decimal fraction
            # (e.g. 1.4875 for 148.75% ROE), while dividendYield already
            # comes back as a percentage number (e.g. 0.35 for 0.35%).
            # Scale ROE to match dividend_yield's units so both fields in
            # the Asset table are consistently "already a percent" -
            # frontend code can display both the same way without needing
            # to remember which one needs *100 and which doesn't.
            "roe": roe_raw * 100 if roe_raw is not None else None,
            "dividend_yield": info.get("dividendYield")
        }

    except YFRateLimitError:
        _record_rate_limit_hit(f"fetch_asset_metadata[{ticker}]")
        return None
    except Exception as e:
        print(f"Error fetching metadata for {ticker}: {e}")
        return None