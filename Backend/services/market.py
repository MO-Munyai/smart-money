# services/market.py

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

        currency = stock.info.get("currency", "ZAR")
        raw_price = float(data["Close"].iloc[-1])
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
            history.append({
                "date": ts.isoformat(),
                "open": normalize_price(ticker, float(row["Open"]), currency),
                "high": normalize_price(ticker, float(row["High"]), currency),
                "low": normalize_price(ticker, float(row["Low"]), currency),
                "close": normalize_price(ticker, float(row["Close"]), currency),
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