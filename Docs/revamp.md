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

- `Asset` model -> becomes the **Instrument** registry. This is the thing that
  gets richer, not thinner.
- `services/market.py`: `get_live_price`, `fetch_asset_metadata` — keep, but
  metadata fetch needs to branch by instrument type (see below).
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
- [ ] **Phase 2 — Data model**: redesign Asset -> Instrument, add `type` +
      type-specific fields, migrate/reset db
- [ ] **Phase 3 — Backend API**: rebuild endpoints around instrument lookup/search
- [ ] **Phase 4 — Frontend**: search/browse/detail UI
- [ ] **Phase 5 — Polish**: history/charting, refresh strategy, comparison view

## Decisions log

- 2026-09-09: Confirmed direction — reference/research tool, not a holdings
  tracker. Scope = stocks, crypto, ETFs, indices. Manual transaction ledger to
  be removed entirely, not replaced with import/simplified holdings entry.
- 2026-09-09: No persisted fundamentals/history at all — always live-fetch.
  Only a lightweight registry table (ticker + type + added_at) persists, so
  "see everything" survives restarts. List view batches live price only;
  full fundamentals fetch is per-instrument on the detail view. No
  watchlist/filters yet — plain "see everything" list for now.
