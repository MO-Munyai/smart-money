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

# Yahoo sometimes quotes a price in a currency's minor unit (cents/pence)
# rather than its major unit - confirmed empirically for South African JSE
# tickers ("ZAc") and British LSE tickers ("GBp"; Yahoo also sometimes uses
# "GBX" for the same thing). Mapped explicitly here (currency code -> real
# major currency + the /100 unit fix) rather than derived by ticker suffix
# or algorithmically from the code, since the minor-unit code doesn't
# mechanically encode its major currency's name (e.g. "ZAc" -> "ZAR" isn't
# a string transform, it's just a fact about what South Africa's currency is
# called). Extend this table if another market turns out to work the same
# way - verify live first, the way these two were.
MINOR_UNIT_CURRENCIES = {
    "ZAc": "ZAR",  # South African cents (JSE)
    "GBp": "GBP",  # British pence (LSE)
    "GBX": "GBP",  # Yahoo's alternate spelling of the same thing
}


def get_price_breakdown(ticker: str, raw_price: float, currency: str) -> dict:
    """
    Full price conversion breakdown: native price (in the instrument's real
    major currency unit), the major currency it's denominated in, the fx
    rate applied (None if none was needed/available), and the final ZAR
    price. normalize_price() is a thin wrapper around this for callers that
    only want the final figure.
    """
    major_currency = currency
    native_price = raw_price

    # Unit fix (minor -> major unit), not a currency conversion - applies
    # before any forex step.
    if currency in MINOR_UNIT_CURRENCIES:
        major_currency = MINOR_UNIT_CURRENCIES[currency]
        native_price = native_price / 100

    fx_rate = None
    zar_price = native_price

    if major_currency.upper() != "ZAR":
        fx_rate = get_forex_rate(major_currency.upper(), "ZAR")
        if fx_rate is not None:
            zar_price = native_price * fx_rate

    return {
        "native_price": native_price,
        "currency": major_currency,
        "fx_rate": fx_rate,
        "zar_price": zar_price
    }


def normalize_price(ticker: str, raw_price: float, currency: str) -> float:
    """
    Converts any stock price to ZAR, handling minor-unit currencies
    (cents/pence) and forex conversion.
    """
    return get_price_breakdown(ticker, raw_price, currency)["zar_price"]