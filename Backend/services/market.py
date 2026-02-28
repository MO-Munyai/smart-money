# services/market.py

import yfinance as yf
import pandas as pd
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


def calculate_portfolio_summary(transactions):
    """
    Generates portfolio summary from a list of transaction objects.
    """
    if not transactions:
        return {
            "total_invested": 0,
            "current_value": 0,
            "total_gain_loss": 0,
            "positions": []
        }

    df = pd.DataFrame([{
        "ticker": t.ticker,
        "quantity": t.quantity if t.type == "buy" else -t.quantity,
        "price": t.price
    } for t in transactions])

    grouped = df.groupby("ticker").agg({
        "quantity": "sum",
        "price": "mean"
    }).reset_index()

    positions = []
    total_invested = 0
    total_current_value = 0

    tickers = grouped["ticker"].tolist()
    live_prices = get_live_prices(tickers)

    for _, row in grouped.iterrows():
        ticker = row["ticker"]
        quantity = row["quantity"]
        if quantity <= 0:
            continue

        avg_price = row["price"]
        invested = quantity * avg_price
        live_price = live_prices.get(ticker)
        if live_price is None:
            continue

        current_value = quantity * live_price

        positions.append({
            "ticker": ticker,
            "quantity": quantity,
            "average_price": avg_price,
            "live_price": live_price,
            "invested": invested,
            "current_value": current_value,
            "gain_loss": current_value - invested
        })

        total_invested += invested
        total_current_value += current_value

    return {
        "total_invested": total_invested,
        "current_value": total_current_value,
        "total_gain_loss": total_current_value - total_invested,
        "positions": positions
    }


def fetch_asset_metadata(ticker: str):
    """
    Fetches fundamental metadata for a given ticker from Yahoo Finance.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        if not info:
            return None

        return {
            "name": info.get("shortName") or info.get("longName") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "beta": info.get("beta"),
            "roe": info.get("returnOnEquity"),
            "dividend_yield": info.get("dividendYield")
        }

    except Exception as e:
        print(f"Error fetching metadata for {ticker}: {e}")
        return None