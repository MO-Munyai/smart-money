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

def get_price_breakdown(ticker: str, raw_price: float, currency: str) -> dict:
    """
    Full price conversion breakdown: native price (after the .JO cents
    adjustment, before forex), the currency it's denominated in, the fx
    rate applied (None if none was needed/available), and the final ZAR
    price. normalize_price() is a thin wrapper around this for callers that
    only want the final figure.
    """
    native_price = raw_price

    # Handle JSE cents - this is a unit fix (cents -> rand), not a currency
    # conversion, so it applies to native_price itself before any forex step.
    if ticker.upper().endswith(".JO"):
        native_price = native_price / 100

    fx_rate = None
    zar_price = native_price

    # "ZAC" (South African cents) is not a foreign currency - it's ZAR
    # itself, just denominated in cents, the same relationship the .JO
    # suffix check already handles for the actual cents math above. Treating
    # it as ZAR-equivalent here avoids a doomed forex lookup for "ZACZAR=X",
    # which isn't a real Yahoo ticker and was previously failing (silently,
    # but noisily logged) on every JSE-ticker fetch.
    if currency.upper() not in ("ZAR", "ZAC"):
        fx_rate = get_forex_rate(currency.upper(), "ZAR")
        if fx_rate is not None:
            zar_price = native_price * fx_rate

    return {
        "native_price": native_price,
        "currency": currency,
        "fx_rate": fx_rate,
        "zar_price": zar_price
    }


def normalize_price(ticker: str, raw_price: float, currency: str) -> float:
    """
    Converts any stock price to ZAR and handles cents vs rands.
    Rules:
    - If ticker ends with .JO (JSE), divide by 100 (cents → rands)
    - Convert non-ZAR currencies to ZAR using forex
    """
    return get_price_breakdown(ticker, raw_price, currency)["zar_price"]