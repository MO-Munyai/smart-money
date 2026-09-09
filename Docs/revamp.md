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
- [ ] **Phase 4 — Frontend**: search/browse/detail UI
  - [x] 4.1 — Register-instrument form: ticker + type input, `POST /instruments`,
        success/error feedback (mirrors the backend's 400/404 cases)
  - [x] 4.2 — Registry table: `GET /instruments`, dataframe with ticker, type,
        live price, added_at
  - [x] 4.3 — Remove-instrument control: pick a row, `DELETE /instruments/{ticker}`
        (bonus bugfix along the way - see decisions log)
  - [ ] 4.4 — Instrument detail view: select a ticker from the registry,
        `GET /instruments/{ticker}`, show fundamentals + live price
  - [ ] 4.5 — Price history chart: `GET /instruments/{ticker}/history` for the
        selected instrument, plotly line/candlestick chart
  - [ ] 4.6 — Comparison view: multi-select 2+ tickers, `GET /instruments/compare`,
        side-by-side metrics table
- [ ] **Phase 5 — Observability & Market Overview**: added mid-Phase-4 after the
      rate-limit discussion. Inserted before the old Phase 5, which is renumbered
      to Phase 6 below.
  - [ ] 5.1 — `services/market.py`: catch `yfinance.exceptions.YFRateLimitError`
        specifically (not just bare `except Exception`) in every fetch function
        (`get_live_price`, `get_live_prices`, `get_price_history`,
        `fetch_asset_metadata`); track a hit count + last-hit timestamp in
        module state and log clearly so a rate-limit hit is distinguishable
        from "ticker doesn't exist" or any other failure
  - [ ] 5.2 — Backend: `GET /health` endpoint exposing app status + the
        rate-limit stats from 5.1
  - [ ] 5.3 — Frontend: new Admin page/section rendering `/health` (rate-limit
        hit count/last-hit-time now; room for more admin info later)
  - [ ] 5.4 — `services/market.py`: expose native price + currency code + the
        fx rate used alongside the existing ZAR-normalized price (new function
        or extended return shape) — `get_live_price` currently discards the
        native price/currency once it converts to ZAR, needed for 5.6's
        dual-currency display
  - [ ] 5.5 — Backend: curated top-10-per-category ticker lists (stocks, ETFs,
        indices, crypto) + `GET /markets/overview` endpoint returning each
        with ZAR price, native price, native currency, and fx rate, grouped
        by category. Open question: curated/static list (simple, no extra
        rate-limit exposure) vs. a dynamic "top by market cap" screener
        (yfinance's screening support is undocumented/inconsistent) — leaning
        curated for now, revisit if it feels stale
  - [ ] 5.6 — Frontend: landing/default view rendering the 4 category tables
        from 5.5 (e.g. "AAPL — ZAR 5,058.74 / USD 230.10 / ZAR-USD 21.98"),
        shown by default ahead of/above the registry-driven sections
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
