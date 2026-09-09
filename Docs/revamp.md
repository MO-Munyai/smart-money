# SmartMoney Revamp

Tracking doc for the pivot away from "budgeting app with a manual buy/sell ledger"
toward "source of truth for stocks and other financial instruments." Use this file
to brainstorm, capture decisions, and track what's actually been done.

## Direction (decided)

- **Not holdings-focused.** No personal portfolio, no positions, no "what do I own."
  This is a research/reference tool: "what do I know about this instrument."
- **Scope:** stocks, crypto, ETFs, indices (all fetchable via yfinance). Bonds,
  cash, commodities explicitly out of scope for now.
- **Core loop:** look up / search an instrument -> see a rich, structured,
  live-refreshed profile of it. The local DB acts as a cache/registry of
  instruments the user has looked up, not a ledger of transactions.

## What gets removed

- `Transaction` model, `crud.create_transaction/get_transactions/delete_transaction`
- `Position` model, `services/portfolio.py` (rebuild_positions_from_transactions, get_positions)
- `/transactions` endpoints, `/portfolio/summary`, `/portfolio/analytics`
- `services/analytics.py` (generate_portfolio_report — gain/loss, weighted metrics
  by position weight all assume holdings)
- `services/market.calculate_portfolio_summary` (dead code already, unused by main.py)
- Frontend: Add Transaction form, Transactions table + delete, Portfolio Summary
  metrics (invested/current value/gain-loss), value-over-time chart
- `portfolio.db` rows for the above tables (fresh schema, see below)

## What survives / evolves

- `Asset` model -> replaced by the identity-only **Instrument** registry
  (`models.py`, `schemas.py`, `crud.py`, `/instruments` endpoints — done in
  Phase 2). No fundamentals persisted; see Data model sketch below.
- `services/market.py`: `get_live_price` (now also used to validate a ticker
  on registration), `get_live_prices`, `fetch_asset_metadata` (unused since
  Phase 2, reserved for the Phase 3 detail-view endpoint).
- `services/currency.py`: normalization still matters for cross-exchange comparison.
- `Docs/Notes.MD` ticker suffix cheat sheet — still relevant, maybe surface in-app.

## Data model sketch (decided)

No fundamentals are persisted — everything (price, history, sector, PE, expense
ratio, etc.) is fetched live from yfinance on demand, for every instrument type
uniformly. That means no wide table, no per-type side tables, no nullable-column
sprawl to argue about.

The only thing that needs to live in the DB is the **registry** — identity only,
so "see everything" persists across restarts instead of resetting every session:
```
Instrument
  id, ticker, type (stock|etf|crypto|index), added_at
```
Adding a ticker to the registry = "I've looked this up, remember it exists."
Everything else about it is fetched fresh every time it's displayed.

Fetch-cost tradeoff this creates: a list view that live-fetches full fundamentals
for every row in the registry will be slow and risks Yahoo rate-limiting as the
registry grows. Split by view:
- **List/registry view**: batch-fetch live price only (`yf.download` takes
  multiple tickers in one call) — cheap, scales fine.
- **Detail view** (single instrument): full live fetch — fundamentals + price +
  history — only when that one instrument is opened.

Open questions:
- Time-based client-side/query caching (e.g. don't re-fetch if fetched <60s ago
  within the same session) to avoid hammering Yahoo on rapid re-renders — worth
  it, or keep it dumb-simple for now and add if rate-limiting becomes a problem?
- Any concept of a "watchlist" (a user-curated shortlist of instruments to
  surface first) — deferred per direction below, revisit later.

## API redesign sketch

- `GET /instruments` — list the registry (ticker, type, batch live price)
- `POST /instruments` — add a ticker to the registry (validates it resolves via yfinance)
- `DELETE /instruments/{ticker}` — remove from registry
- `GET /instruments/{ticker}` — full live profile: fundamentals + price
- `GET /instruments/{ticker}/history?period=` — live OHLC series for charting
- `GET /instruments/compare?tickers=A,B,C` — side-by-side live metrics
- Drop everything under `/transactions` and `/portfolio/*`

## Frontend redesign sketch

Replace transaction form + portfolio dashboard with:
- Search/add bar (ticker -> fetch & register if not already known)
- Instrument registry table (sortable/filterable by type, sector, country)
- Instrument detail view: price chart, key metrics, peer/sector context
- Maybe: comparison view for 2+ tickers side by side

## Execution phases

- [x] **Phase 0 — Brainstorm & scope** (this doc)
- [x] **Phase 1 — Strip the ledger**: removed Transaction/Position models,
      `/transactions` and `/portfolio/*` endpoints, `services/portfolio.py`,
      `services/analytics.py`, dead `calculate_portfolio_summary` in
      `services/market.py`, and the transaction form / table / portfolio
      dashboard sections from the frontend (now a placeholder page). Left
      `Asset` model + `/assets` endpoints as-is — that redesign is Phase 2.
- [x] **Phase 2 — Data model**: `Asset` -> identity-only `Instrument`
      (ticker, type, added_at), no persisted fundamentals. Landed as 4
      commits: model, schema, crud, then `/instruments` endpoints
      (POST validates the ticker resolves via live price before registering).
- [x] **Phase 3 — Backend API**: rebuild endpoints around instrument lookup/search.
      All 5 sub-tasks verified live (real yfinance calls, not just import checks),
      then manually confirmed end-to-end by the user running backend+frontend.
      Known open item: `compare` (3.5) doesn't check the registry like 3.2/3.3
      do - it'll fetch/compare any resolvable ticker whether registered or not.
      Left as-is; revisit if it should be registry-gated for consistency.
  - [x] 3.1 — `services/market.py`: add `get_price_history(ticker, period, interval)`
        (OHLC series, ZAR-normalized like `get_live_price`) — needed by 3.3
  - [x] 3.2 — `GET /instruments/{ticker}`: full live profile (fundamentals via
        `fetch_asset_metadata` + live price), 404 if ticker isn't registered
  - [x] 3.3 — `GET /instruments/{ticker}/history?period=&interval=`: OHLC
        series for charting, using 3.1
  - [x] 3.4 — `GET /instruments` (list): enrich each row with a batch-fetched
        live price (`get_live_prices`) instead of returning bare registry rows
  - [x] 3.5 — `GET /instruments/compare?tickers=A,B,C`: side-by-side live
        metrics for 2+ tickers (must be routed before 3.2's `{ticker}` path
        or FastAPI will treat "compare" as a ticker)
- [x] **Phase 4 — Frontend**: search/browse/detail UI
  - [x] 4.1 — Register-instrument form: ticker + type input, `POST /instruments`,
        success/error feedback (mirrors the backend's 400/404 cases)
  - [x] 4.2 — Registry table: `GET /instruments`, dataframe with ticker, type,
        live price, added_at
  - [x] 4.3 — Remove-instrument control: pick a row, `DELETE /instruments/{ticker}`
        (bonus bugfix along the way - see decisions log)
  - [x] 4.4 — Instrument detail view: select a ticker from the registry,
        `GET /instruments/{ticker}`, show fundamentals + live price
  - [x] 4.5 — Price history chart: `GET /instruments/{ticker}/history` for the
        selected instrument, plotly line/candlestick chart
  - [x] 4.6 — Comparison view: multi-select 2+ tickers, `GET /instruments/compare`,
        side-by-side metrics table
- [ ] **Phase 5 — Observability & Market Overview**: added mid-Phase-4 after the
      rate-limit discussion. Inserted before the old Phase 5, which is renumbered
      to Phase 6 below.
  - [x] 5.1 — `services/market.py`: catch `yfinance.exceptions.YFRateLimitError`
        specifically (not just bare `except Exception`) in every fetch function
        (`get_live_price`, `get_live_prices`, `get_price_history`,
        `fetch_asset_metadata`); track a hit count + last-hit timestamp in
        module state and log clearly so a rate-limit hit is distinguishable
        from "ticker doesn't exist" or any other failure
  - [x] 5.2 — Backend: `GET /health` endpoint exposing app status + the
        rate-limit stats from 5.1
  - [x] 5.3 — Frontend: new Admin page/section rendering `/health` (rate-limit
        hit count/last-hit-time now; room for more admin info later)
  - [x] 5.4 — `services/market.py`: expose native price + currency code + the
        fx rate used alongside the existing ZAR-normalized price (new function
        or extended return shape) — `get_live_price` currently discards the
        native price/currency once it converts to ZAR, needed for 5.6's
        dual-currency display
  - [ ] 5.5 — Backend: top-10-per-category ticker lists (stocks, ETFs, indices,
        crypto) + `GET /markets/overview` endpoint returning each with ZAR
        price, native price, native currency, and fx rate, grouped by
        category. Per 5.7's findings: `yf.screen()` / `PREDEFINED_SCREENER_QUERIES`
        actually works live and is viable for the stocks category (e.g.
        `most_actives`, `day_gainers`); no crypto/ETF/index equivalent exists,
        so those three categories still need a curated/static list. Decide
        the stocks-category approach (screener vs. curated, for consistency)
        when this task is picked up
  - [ ] 5.6 — Frontend: landing/default view rendering the 4 category tables
        from 5.5 (e.g. "AAPL — ZAR 5,058.74 / USD 230.10 / ZAR-USD 21.98"),
        shown by default ahead of/above the registry-driven sections
  - [x] 5.7 — yfinance deep-dive: comprehensive empirical research beyond our
        current scope - latency (history/info/batch download), rate-limit
        thresholds and recovery time, batch NaN + weekend/holiday semantics,
        the `ZAC` vs `ZAR` currency quirk, per-instrument-type field coverage,
        error taxonomy (`yfinance.exceptions`), and a capability inventory
        (dividends/splits, earnings, options, financials, screener, etc.) so
        we're not flying blind on an undocumented/scraped API. Written up as
        `Docs/yfinance-notes.md`. Findings split into concrete fix tasks below.
  - [ ] 5.8 — `get_live_prices`: replace the blind `.iloc[-1]` with
        `dropna().iloc[-1]` per ticker (last non-NaN value in the fetched
        window), guarding all-NaN -> `None`. Per 5.7: NOT a weekend/holiday
        issue and does NOT need a wider window - `period="1d"` is already
        sufficient once `.iloc[-1]` stops being trusted blindly; the NaN
        comes from mixing 24/7 crypto with market-hours equities in one
        batch call. No persistence involved either way.
  - [x] 5.9 — `services/currency.py` `normalize_price`/`get_price_breakdown`:
        treat `ZAC` as `ZAR`-equivalent (skip the forex lookup for it)
        instead of trying a `ZACZAR=X` conversion that doesn't exist on
        Yahoo. Per 5.7 finding 3 - `ZAC` is just ZAR-in-cents, same
        relationship the `.JO` suffix check already handles for the cents
        math. Done ahead of order (was next up after 5.4) after the user hit
        the noisy failed lookup live in server logs.
  - [ ] 5.10 — `fetch_asset_metadata`: fix the invalid-ticker check. Per 5.7's
        bonus finding, `if not info` never fires for a bad/delisted ticker -
        Yahoo returns a non-empty degenerate dict (`{'trailingPegRatio': None}`),
        not an empty one - so `GET /instruments/{ticker}` and `/compare`
        currently return a mostly-blank "profile" instead of a proper error.
        Use a better validity check (e.g. require `shortName`/`longName`/
        `regularMarketPrice` to be present).
- [ ] **Phase 6 — Polish** *(renumbered from Phase 5)*: history/charting,
      refresh strategy, comparison view

## Decisions log

- 2026-09-09: Confirmed direction — reference/research tool, not a holdings
  tracker. Scope = stocks, crypto, ETFs, indices. Manual transaction ledger to
  be removed entirely, not replaced with import/simplified holdings entry.
- 2026-09-09: No persisted fundamentals/history at all — always live-fetch.
  Only a lightweight registry table (ticker + type + added_at) persists, so
  "see everything" survives restarts. List view batches live price only;
  full fundamentals fetch is per-instrument on the detail view. No
  watchlist/filters yet — plain "see everything" list for now.
- 2026-09-09: Added Phase 5 (Observability & Market Overview) mid-Phase-4,
  inserted before the old Phase 5 which became Phase 6. Triggered by a
  question about whether Yahoo rate-limiting could be monitored - answer:
  no proactive headroom visibility (Yahoo doesn't expose that), so the fix is
  distinguishing `YFRateLimitError` from generic failures and tracking/logging
  it, surfaced on a new admin page. Same phase also covers a new
  default-landing-page requirement: top 10 stocks/ETFs/indices/crypto shown
  with both ZAR and native-currency price plus the fx rate used.
- 2026-09-09: Bug found while testing 4.3 - `GET /instruments` 500'd
  ("Out of range float values are not JSON compliant: nan"). Root cause:
  `yf.download`'s batched multi-ticker mode returns NaN for a ticker's Close
  when its market didn't trade that day (e.g. AAPL/MSFT vs a JSE ticker in
  the same batch); `get_live_prices` never checked for NaN, so it flowed
  straight into the JSON response and crashed serialization. Fixed by
  NaN-guarding `get_live_price`, `get_live_prices`, and `get_price_history`
  in `services/market.py` (NaN -> `None` price / skipped history bar,
  matching how "no data" is already handled elsewhere). Also observed the
  batch path (`get_live_prices`) is noticeably less reliable than the
  singular path (`get_live_price`) even for liquid tickers like AAPL/MSFT -
  worth keeping an eye on alongside the Phase 5 rate-limit work, since it
  may be the same underlying Yahoo throttling rather than a separate issue.
- 2026-09-09: 5.7's research (`Docs/yfinance-notes.md`) resolved the above -
  it's NOT throttling and NOT a weekend/holiday gap. `period="1d"` singular
  calls are reliable; the batch path's NaN is caused by mixing 24/7 crypto
  with market-hours equities in one `yf.download()` call, which extends the
  shared date index to include "today" - genuinely absent for equities that
  haven't traded yet. Fix is `dropna().iloc[-1]` (5.8), not a wider window -
  confirmed widening the window actually introduces a *new* NaN (the most
  recent day's still-forming candle) rather than fixing anything. Also
  confirmed the `ZAC` currency bug's mechanics (5.9) and found a bonus bug:
  `fetch_asset_metadata`'s invalid-ticker check never fires because Yahoo
  returns a non-empty degenerate dict for bad tickers, not an empty one
  (5.10). Rate-limit burst test (40 requests) triggered no throttling.
  Screener API (`yf.screen()`) confirmed working, revises 5.5's stocks-category
  approach from "curated only" to "screener viable for stocks, curated still
  needed for ETF/index/crypto."
- 2026-09-09: Expanded 5.2's `/health` into a real diagnostics endpoint per
  user request: uptime, DB reachability + latency + instrument count, Python
  version/platform, and process memory/CPU via `psutil` (new dependency,
  added to `backend_requirements.txt`, gracefully degrades if not yet
  installed). Live Yahoo reachability check is opt-in (`?deep=true`) rather
  than always-on - an admin page auto-polling `/health` shouldn't itself
  become yfinance traffic contributing to the exact rate-limit problem 5.1
  exists to track. `status` aggregates to "degraded" if DB or (when deep)
  market data isn't reachable. Verified live: cheap mode fast with real
  instrument count (5) and process stats (137MB), deep mode's yfinance
  round-trip measured at ~2.6s, consistent with earlier latency research.
- 2026-09-09: Built 5.3 as a real Streamlit multi-page app rather than another
  section on the main page - `Frontend/pages/Admin.py`, auto-discovered by
  Streamlit's `pages/` convention. Extracted `api_request`/`error_detail`/
  `safe_json`/`API_URL` out of `app.py` into a new shared `Frontend/api_client.py`
  first, since each Streamlit page runs as its own script and can't share
  in-file helpers otherwise - future pages should import from there rather
  than redefining these. Admin page has a manual Refresh button and an
  opt-in "Deep check" checkbox (maps to `/health?deep=true`) rather than
  auto-polling, for the same rate-limit-exposure reason 5.2's deep mode is
  opt-in. Verified the actual data-handling logic (not just that the routes
  return 200) directly against the live backend - confirmed response keys
  match what the page reads, `format_uptime()` converts correctly, and the
  deep checkbox's boolean actually reaches FastAPI's `deep: bool` query
  param correctly (`?deep=True` parses truthy, deep check fires for real).
- 2026-09-09: 5.4 - added `services/currency.py` `get_price_breakdown()`
  (native price, currency, fx rate applied, zar price), with `normalize_price()`
  refactored into a thin wrapper around it. `services/market.py` got a new
  `get_live_price_detail()` using the breakdown; `get_live_price()` itself
  refactored to be a thin wrapper around that, so there's one fetch code path
  instead of two. Verified byte-for-byte regression (AAPL/NPN.JO/BTC-USD):
  `get_live_price()`'s output exactly matches `detail["zar_price"]` in every
  case. Also caught this live: `NPN.JO`'s `zar_price` is correct today only
  because the still-broken `ZACZAR=X` forex lookup (5.9) fails and "no rate
  found" happens to default to "apply no conversion" - accidentally right,
  not intentionally. 5.9 will make that explicit rather than relying on the
  lookup failing usefully.
- 2026-09-09: User reported the Instrument Registry section "failing" after
  4.4, backend logs showing NaN. The market.py NaN guard from 4.3 was already
  live and working (confirmed - `GET /instruments` returns 200 with `null`
  prices, not a 500). Real bug found: `Frontend/app.py`'s error branches
  called `response.json()` unguarded - FastAPI's default handler returns
  **plain text**, not JSON, for an unhandled exception, so `.json()` itself
  raised and crashed the whole Streamlit page with an unrelated
  `JSONDecodeError`, on top of whatever the original error was. Fixed with a
  shared `error_detail()` helper (falls back to `.text` when `.json()`
  fails) used at all four `.json()`-on-error call sites, plus guarding the
  registry list's own `r.json()` parse. Not tied to a specific phase task -
  logged here since it's a standalone frontend robustness fix.
- 2026-09-09: User asked for blanket error handling, backend and frontend,
  everywhere something can break. Backend: rather than wrapping every
  endpoint body individually, added one global `@app.exception_handler(Exception)`
  in `main.py` - catches anything not already an `HTTPException` (e.g. a DB
  error) and returns proper `{"detail": ...}` JSON instead of FastAPI's
  default plain-text 500. This also closes the loop on the earlier
  `response.json()` frontend crash from the other direction - even without
  the frontend's `error_detail()` fallback, the backend now never sends a
  non-JSON error body in the first place. Verified: existing 404/400
  `HTTPException` responses unaffected, and a simulated unhandled exception
  returns clean JSON. Frontend half done too: added `api_request()` wrapping
  every `requests.*` call in `app.py` against `requests.exceptions.RequestException`
  (connection refused, timeout, DNS failure) - the case `error_detail()`
  didn't cover, since that only handles "got a response but it errored," not
  "never got a response at all." Also added `safe_json()` for response bodies
  on the success path. Verified both branches directly: pointed at an
  unreachable port -> `(None, "Could not reach backend: ...")` instead of
  raising; pointed at the real running backend -> normal 200 response.
  Between this and the backend's global handler, every network/parse boundary
  in both frontend and backend now degrades to a message instead of crashing.
- 2026-09-09: User asked to add minute/hour interval options to 4.5's history
  chart (1m/5m/10m/15m/30m/1h/3h/6h/12h). Tested against the live API first -
  `10m`/`3h`/`6h`/`12h` aren't valid Yahoo intervals at all (confirmed
  Yahoo's actual set: `1m,2m,5m,15m,30m,1h,4h,1d,5d,1wk,1mo,3mo` - invalid
  ones don't error, they silently return 0 rows). Used `4h` in place of
  `3h`/`6h`/`12h` since it's the only sub-daily option beyond `1h` Yahoo
  offers. Also confirmed real depth limits per interval (1m -> 8 days max,
  5m/15m/30m -> 60 days max, 1h/4h -> 2y+ fine) - so made the Period dropdown
  depend on the selected Interval, keyed per-interval
  (`history_period_{interval}`) to avoid Streamlit raising when a cached
  widget value isn't in a newly-changed options list. Every interval/period
  combination in the resulting UI was individually curl-tested against the
  real backend and confirmed to return actual bars, both at defaults and at
  each interval's max-period boundary.
