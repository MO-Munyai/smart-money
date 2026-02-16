import yfinance as yf

# Cache for forex rates to reduce repeated calls
FOREX_CACHE = {}

def get_forex_rate(from_currency: str, to_currency: str = "ZAR"):
    """
    Returns conversion rate from 'from_currency' to 'to_currency'
    using Yahoo Finance USDZAR-style tickers.
    """
    if from_currency == to_currency:
        return 1.0

    key = f"{from_currency}_{to_currency}"
    if key in FOREX_CACHE:
        return FOREX_CACHE[key]

    # Yahoo uses ticker like "USDZAR=X" for forex rates
    ticker = f"{from_currency}{to_currency}=X"
    try:
        fx = yf.Ticker(ticker)
        data = fx.history(period="1d")
        if data.empty:
            return None
        rate = float(data["Close"].iloc[-1])
        FOREX_CACHE[key] = rate
        return rate
    except Exception:
        return None

def normalize_price(ticker: str, raw_price: float, currency: str) -> float:
    """
    Converts any stock price to ZAR and handles cents vs rands.
    Rules:
    - If ticker ends with .JO (JSE), divide by 100 (cents → rands)
    - Convert non-ZAR currencies to ZAR using forex
    """
    price = raw_price

    # Handle JSE cents
    if ticker.upper().endswith(".JO"):
        price = price / 100  # cents → rands

    # Convert to ZAR if not ZAR
    if currency.upper() != "ZAR":
        rate = get_forex_rate(currency.upper(), "ZAR")
        if rate is not None:
            price = price * rate

    return price