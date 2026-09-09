# services/market.py

import math
import yfinance as yf
from services.currency import normalize_price


def get_live_price(ticker: str):
    """
    Fetches live price for a single ticker with currency normalization.
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
        return normalize_price(ticker, raw_price, currency)
    except Exception:
        return None


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
            except Exception:
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
    except Exception as e:
        print(f"Error fetching history for {ticker}: {e}")
        return []


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

    except Exception as e:
        print(f"Error fetching metadata for {ticker}: {e}")
        return None