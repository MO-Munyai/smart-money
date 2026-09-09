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
# (see Docs/yfinance-notes.md), so all categories use a fixed list for
# consistency rather than mixing a dynamic screener for stocks with curated
# lists for the rest.
#
# Currency AND display name are both hardcoded per ticker rather than looked
# up live: an instrument's quote currency and name essentially never change,
# and looking currency up via .info was the dominant cost of this endpoint -
# confirmed live, doing it for the first 40 tickers took ~57s vs ~12s once
# removed (get_live_price_detail still looks currency up live for
# user-registered instruments, since those aren't a fixed list). All
# tickers/currencies/names below verified against real yfinance data on
# 2026-09-09. Price itself is always still fetched live, every request.
#
# Currency codes are the RAW Yahoo values (e.g. "ZAc", "GBp") - get_price_breakdown
# (services/currency.py) handles minor-unit conversion generically now.
CURATED_MARKETS = {
    "stocks": [
        ("AAPL", "USD", "Apple Inc."), ("MSFT", "USD", "Microsoft Corporation"),
        ("GOOGL", "USD", "Alphabet Inc."), ("AMZN", "USD", "Amazon.com, Inc."),
        ("NVDA", "USD", "NVIDIA Corporation"), ("META", "USD", "Meta Platforms, Inc."),
        ("TSLA", "USD", "Tesla, Inc."), ("BRK-B", "USD", "Berkshire Hathaway Inc."),
        ("JPM", "USD", "JPMorgan Chase & Co."), ("V", "USD", "Visa Inc."),
    ],
    "etfs": [
        ("SPY", "USD", "SPDR S&P 500 ETF Trust"), ("QQQ", "USD", "Invesco QQQ Trust"),
        ("VOO", "USD", "Vanguard S&P 500 ETF"), ("VTI", "USD", "Vanguard Total Stock Market ETF"),
        ("IVV", "USD", "iShares Core S&P 500 ETF"), ("GLD", "USD", "SPDR Gold Shares"),
        ("VYM", "USD", "Vanguard High Dividend Yield ETF"), ("SCHD", "USD", "Schwab US Dividend Equity ETF"),
        ("ARKK", "USD", "ARK Innovation ETF"), ("XLK", "USD", "Technology Select Sector SPDR Fund"),
    ],
    "indices": [
        ("^GSPC", "USD", "S&P 500"), ("^DJI", "USD", "Dow Jones Industrial Average"),
        ("^IXIC", "USD", "NASDAQ Composite"), ("^RUT", "USD", "Russell 2000"),
        ("^VIX", "USD", "CBOE Volatility Index"), ("^FTSE", "GBP", "FTSE 100"),
        ("^N225", "JPY", "Nikkei 225"), ("^GDAXI", "EUR", "DAX"),
        ("^HSI", "HKD", "Hang Seng Index"), ("^STOXX50E", "EUR", "EURO STOXX 50"),
    ],
    "crypto": [
        ("BTC-USD", "USD", "Bitcoin"), ("ETH-USD", "USD", "Ethereum"),
        ("SOL-USD", "USD", "Solana"), ("BNB-USD", "USD", "BNB"),
        ("XRP-USD", "USD", "XRP"), ("ADA-USD", "USD", "Cardano"),
        ("DOGE-USD", "USD", "Dogecoin"), ("AVAX-USD", "USD", "Avalanche"),
        ("DOT-USD", "USD", "Polkadot"), ("LINK-USD", "USD", "Chainlink"),
    ],
}

# Country/market groupings for the same overview. "US" reuses CURATED_MARKETS
# ["stocks"] verbatim rather than duplicating it, so those 10 tickers are
# only ever fetched once per overview call. The other four markets have no
# overlap with any type-based list, so they're fetched separately - each
# ranked by real market cap (or, for Australia, well-known ASX blue-chip
# ranking - Yahoo's marketCap field was missing for half the candidates),
# confirmed live on 2026-09-09. South Africa and UK include dual/foreign-listed
# names (BHP Group, Richemont on the JSE; Shell, Unilever on the LSE),
# consistent with how "top 40"-style local-market lists are normally
# presented, not filtered to only domestically-domiciled companies.
CURATED_COUNTRIES = {
    "US": [(t, c, n) for t, c, n in CURATED_MARKETS["stocks"]],
    "South Africa": [
        ("BHG.JO", "ZAc", "BHP Group Limited"), ("CFR.JO", "ZAc", "Compagnie Financiere Richemont"),
        ("PRX.JO", "ZAc", "Prosus N.V."), ("AGL.JO", "ZAc", "Anglo American plc"),
        ("NPN.JO", "ZAc", "Naspers Limited"), ("CPI.JO", "ZAc", "Capitec Bank Holdings"),
        ("FSR.JO", "ZAc", "FirstRand Limited"), ("SBK.JO", "ZAc", "Standard Bank Group"),
        ("MTN.JO", "ZAc", "MTN Group Limited"), ("VOD.JO", "ZAc", "Vodacom Group Limited"),
    ],
    "United Kingdom": [
        ("AZN.L", "GBp", "AstraZeneca PLC"), ("SHEL.L", "GBp", "Shell PLC"),
        ("HSBA.L", "GBp", "HSBC Holdings PLC"), ("ULVR.L", "GBp", "Unilever PLC"),
        ("BP.L", "GBp", "BP PLC"), ("GSK.L", "GBp", "GSK PLC"),
        ("RIO.L", "GBp", "Rio Tinto PLC"), ("DGE.L", "GBp", "Diageo PLC"),
        ("REL.L", "GBp", "RELX PLC"), ("BATS.L", "GBp", "British American Tobacco PLC"),
    ],
    "Europe": [
        ("ASML.AS", "EUR", "ASML Holding N.V."), ("MC.PA", "EUR", "LVMH"),
        ("NESN.SW", "CHF", "Nestle S.A."), ("OR.PA", "EUR", "L'Oreal"),
        ("SIE.DE", "EUR", "Siemens AG"), ("TTE.PA", "EUR", "TotalEnergies SE"),
        ("SAN.PA", "EUR", "Sanofi"), ("RMS.PA", "EUR", "Hermes International"),
        ("SAP.DE", "EUR", "SAP SE"), ("NOVO-B.CO", "DKK", "Novo Nordisk A/S"),
    ],
    "Australia": [
        ("BHP.AX", "AUD", "BHP Group"), ("CBA.AX", "AUD", "Commonwealth Bank of Australia"),
        ("CSL.AX", "AUD", "CSL Limited"), ("NAB.AX", "AUD", "National Australia Bank"),
        ("WBC.AX", "AUD", "Westpac Banking Corporation"), ("ANZ.AX", "AUD", "ANZ Group Holdings"),
        ("WES.AX", "AUD", "Wesfarmers Limited"), ("MQG.AX", "AUD", "Macquarie Group"),
        ("WOW.AX", "AUD", "Woolworths Group"), ("TLS.AX", "AUD", "Telstra Group"),
    ],
}


def _fetch_curated_entry(ticker: str, currency: str, name: str):
    """
    Live price + conversion breakdown for one curated ticker, with the
    same NaN/error handling as the rest of services/market.py. Currency and
    name are passed in (hardcoded per curated ticker, verified live) rather
    than looked up via .info - see CURATED_MARKETS' comment for why.
    """
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")
        if data.empty:
            return {"ticker": ticker, "name": name, "error": "no data"}

        raw_price = float(data["Close"].iloc[-1])
        if math.isnan(raw_price):
            return {"ticker": ticker, "name": name, "error": "no data"}

        breakdown = get_price_breakdown(ticker, raw_price, currency)
        return {"ticker": ticker, "name": name, **breakdown}
    except YFRateLimitError:
        _record_rate_limit_hit(f"get_market_overview[{ticker}]")
        return {"ticker": ticker, "name": name, "error": "rate limited"}
    except Exception as e:
        print(f"Error fetching overview price for {ticker}: {e}")
        return {"ticker": ticker, "name": name, "error": "fetch failed"}


def get_market_overview():
    """
    Live price breakdown (name, native price, currency, fx rate, ZAR price)
    for the curated top-10 lists, grouped two ways: by instrument type
    (stocks/etfs/indices/crypto) and by country/market (US, South Africa,
    United Kingdom, Europe, Australia). Returns
    {"by_type": {...}, "by_country": {...}}, each entry either
    {ticker, name, native_price, currency, fx_rate, zar_price} or
    {ticker, name, error} if that ticker failed.
    """
    by_type = {}
    fetched_by_ticker = {}
    for category, entries in CURATED_MARKETS.items():
        results = []
        for ticker, currency, name in entries:
            entry = _fetch_curated_entry(ticker, currency, name)
            fetched_by_ticker[ticker] = entry
            results.append(entry)
        by_type[category] = results

    by_country = {
        # Already fetched above as CURATED_MARKETS["stocks"] - reuse, don't refetch.
        "US": [fetched_by_ticker[ticker] for ticker, _, _ in CURATED_COUNTRIES["US"]],
    }
    for country, entries in CURATED_COUNTRIES.items():
        if country == "US":
            continue
        by_country[country] = [
            _fetch_curated_entry(ticker, currency, name)
            for ticker, currency, name in entries
        ]

    return {"by_type": by_type, "by_country": by_country}


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