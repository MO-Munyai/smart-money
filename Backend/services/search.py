# services/search.py

import yfinance as yf
from yfinance.exceptions import YFRateLimitError
from services.market import _record_rate_limit_hit

# Yahoo's own quoteType values, mapped onto this app's InstrumentType enum
# (schemas.py). Anything not listed here (FUTURE, OPTION, MUTUALFUND,
# CURRENCY, ...) is out of the revamp's scope (stocks/ETFs/crypto/indices
# only) and silently dropped from search results.
QUOTE_TYPE_MAP = {
    "EQUITY": "Stock",
    "ETF": "ETF",
    "CRYPTOCURRENCY": "Crypto",
    "INDEX": "Index",
}

# Yahoo exchange code -> country/market. Built from live empirical testing
# (searching real companies across continents - see Docs/revamp.md 6.x
# decisions log), not guessed. Not exhaustive: Yahoo covers hundreds of
# exchanges worldwide. An exchange code not listed here falls back to an
# "Other" bucket, using Yahoo's own exchange display name as the value,
# rather than being silently hidden from results.
EXCHANGE_COUNTRY_MAP = {
    # United States
    "NMS": "United States", "NYQ": "United States", "NGM": "United States",
    "NCM": "United States", "NAS": "United States", "PCX": "United States",
    "BTS": "United States", "PNK": "United States", "ASE": "United States",
    # South Africa
    "JNB": "South Africa",
    # United Kingdom
    "LSE": "United Kingdom", "IOB": "United Kingdom",
    # Japan
    "JPX": "Japan", "OSA": "Japan",
    # Germany
    "FRA": "Germany", "GER": "Germany", "DUS": "Germany", "HAM": "Germany",
    "MUN": "Germany", "STU": "Germany", "BER": "Germany",
    # France
    "PAR": "France",
    # Netherlands
    "AMS": "Netherlands",
    # Switzerland
    "EBS": "Switzerland",
    # Australia
    "ASX": "Australia",
    # Hong Kong
    "HKG": "Hong Kong",
    # China
    "SHH": "China", "SHZ": "China",
    # India
    "BSE": "India", "NSI": "India",
    # Singapore
    "SES": "Singapore",
    # Thailand
    "SET": "Thailand",
    # Canada
    "TOR": "Canada", "VAN": "Canada",
    # Brazil
    "SAO": "Brazil",
    # Argentina
    "BUE": "Argentina",
    # Spain
    "MCE": "Spain",
    # Austria
    "VIE": "Austria",
    # Hungary
    "BUD": "Hungary",
    # Malaysia
    "KLS": "Malaysia",
    # South Korea
    "KSC": "South Korea", "KOE": "South Korea",
    # Crypto has no real country - Yahoo quotes it on its own venue ("CCC")
    "CCC": "Crypto",
}

# Yahoo's search has no server-side type/country filter, so we over-fetch
# raw matches and filter client-side - this is how many of those survive
# well enough even after a type/country filter knocks some out.
_RAW_FETCH_COUNT = 30


def get_known_types():
    """In-scope instrument types, for the frontend's type filter dropdown."""
    return list(QUOTE_TYPE_MAP.values())


def get_known_countries():
    """
    Distinct countries this app can currently filter by, derived from
    EXCHANGE_COUNTRY_MAP (single source of truth - the frontend doesn't
    hardcode its own copy), plus "Other" for anything that map doesn't
    cover yet.
    """
    return sorted(set(EXCHANGE_COUNTRY_MAP.values())) + ["Other"]


def _resolve_country(exchange, exch_disp):
    if not exchange:
        return exch_disp or "Other"
    return EXCHANGE_COUNTRY_MAP.get(exchange, exch_disp or "Other")


def search_instruments(query: str, type_filter: str = None, country_filter: str = None, limit: int = 15):
    """
    Live instrument search via Yahoo's own search/autocomplete endpoint - no
    local index, consistent with the rest of the app's "always live-fetch"
    data model (see Docs/revamp.md). Maps quoteType down to this app's 4
    in-scope types and derives a country from the exchange code, then
    applies the optional type/country filters (Yahoo's API doesn't support
    either server-side).

    Returns a list of {ticker, name, type, exchange, country} dicts,
    truncated to `limit` after filtering.
    """
    query = (query or "").strip()
    if not query:
        return []

    try:
        quotes = yf.Search(query, max_results=_RAW_FETCH_COUNT).quotes
    except YFRateLimitError:
        _record_rate_limit_hit(f"search_instruments[{query}]")
        return []
    except Exception as e:
        print(f"Error searching instruments for '{query}': {e}")
        return []

    results = []
    for q in quotes:
        mapped_type = QUOTE_TYPE_MAP.get(q.get("quoteType"))
        if mapped_type is None:
            continue
        if type_filter and mapped_type != type_filter:
            continue

        country = _resolve_country(q.get("exchange"), q.get("exchDisp"))
        if country_filter and country != country_filter:
            continue

        results.append({
            "ticker": q.get("symbol"),
            "name": q.get("longname") or q.get("shortname") or q.get("symbol"),
            "type": mapped_type,
            "exchange": q.get("exchDisp"),
            "country": country,
        })

        if len(results) >= limit:
            break

    return results
