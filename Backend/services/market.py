import yfinance as yf
import pandas as pd


def get_live_price(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")
        if data.empty:
            return None
        return float(data["Close"].iloc[-1])
    except Exception:
        return None


def calculate_portfolio_summary(transactions):
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

    for _, row in grouped.iterrows():
        ticker = row["ticker"]
        quantity = row["quantity"]

        if quantity <= 0:
            continue

        avg_price = row["price"]
        invested = quantity * avg_price
        live_price = get_live_price(ticker)

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