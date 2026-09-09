# Backend/main.py
import platform
import sys
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import models
import schemas
import crud
from database import SessionLocal, engine
from services.market import (
    get_live_price, get_live_prices, get_price_history, fetch_asset_metadata,
    get_rate_limit_state, get_market_overview
)

# Create DB tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="SmartMoney v0.3")

_start_time = time.monotonic()
_started_at = datetime.now(timezone.utc)


# Catches anything not already turned into an HTTPException below (e.g. a DB
# error) so it comes back as {"detail": ...} JSON instead of FastAPI's
# default plain-text 500 - which broke the frontend's response.json() calls
# even after the underlying bug (services/market.py NaN) was already fixed.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    print(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"detail": f"Internal error: {exc}"})

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------
# Health
# -------------------------------
@app.get("/health")
def health(deep: bool = False, db: Session = Depends(get_db)):
    """
    System diagnostics. Cheap by default (uptime, DB reachability, rate-limit
    stats, process info) - pass ?deep=true to additionally verify Yahoo
    Finance itself is reachable right now. Deep is opt-in on purpose: it
    makes a real yfinance call, so an admin page auto-polling /health
    shouldn't do that on every refresh and become rate-limit exposure of
    its own (see 5.1).
    """
    db_start = time.monotonic()
    try:
        instrument_count = db.query(models.Instrument).count()
        database = {
            "reachable": True,
            "instrument_count": instrument_count,
            "latency_ms": round((time.monotonic() - db_start) * 1000, 2)
        }
    except Exception as e:
        database = {"reachable": False, "error": str(e)}

    system = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform()
    }
    try:
        import psutil
        process = psutil.Process()
        system["process_memory_mb"] = round(process.memory_info().rss / (1024 * 1024), 2)
        system["process_cpu_percent"] = process.cpu_percent(interval=0.1)
    except ImportError:
        system["process_stats"] = "psutil not installed - pip install -r backend_requirements.txt"

    rate_limit = get_rate_limit_state()

    result = {
        "status": "ok" if database["reachable"] else "degraded",
        "uptime_seconds": round(time.monotonic() - _start_time, 1),
        "started_at": _started_at,
        "checked_at": datetime.now(timezone.utc),
        "database": database,
        "rate_limit": {
            "hits": rate_limit["hits"],
            "last_hit_at": rate_limit["last_hit_at"]
        },
        "system": system
    }

    if deep:
        market_start = time.monotonic()
        price = get_live_price("AAPL")
        market_reachable = price is not None
        result["market_data"] = {
            "reachable": market_reachable,
            "checked_ticker": "AAPL",
            "latency_ms": round((time.monotonic() - market_start) * 1000, 2)
        }
        if not market_reachable:
            result["status"] = "degraded"

    return result


# -------------------------------
# Markets Overview
# -------------------------------
@app.get("/markets/overview")
def markets_overview():
    """
    Live price breakdown for the curated top-10 stocks/ETFs/indices/crypto,
    grouped by category. Powers the default landing view (5.6). Takes ~10s+
    to fetch all 40 tickers live (no persistence) - callers should expect
    that and treat it as a background/deferred load, not an instant one.
    """
    return get_market_overview()


# -------------------------------
# Instruments Endpoints
# -------------------------------
@app.post("/instruments", response_model=schemas.Instrument)
def add_instrument(instrument: schemas.InstrumentCreate, db: Session = Depends(get_db)):
    if crud.get_instrument_by_ticker(db, instrument.ticker):
        raise HTTPException(status_code=400, detail="Instrument already registered")
    if get_live_price(instrument.ticker) is None:
        raise HTTPException(status_code=404, detail="Ticker not found")
    return crud.create_instrument(db, instrument)


@app.get("/instruments")
def list_instruments(db: Session = Depends(get_db)):
    instruments = crud.get_instruments(db)
    prices = get_live_prices([i.ticker for i in instruments]) if instruments else {}
    return [
        {
            "id": i.id,
            "ticker": i.ticker,
            "type": i.type,
            "added_at": i.added_at,
            "live_price": prices.get(i.ticker)
        }
        for i in instruments
    ]


@app.delete("/instruments/{ticker}")
def remove_instrument(ticker: str, db: Session = Depends(get_db)):
    if not crud.delete_instrument(db, ticker):
        raise HTTPException(status_code=404, detail="Instrument not found")
    return {"message": "Instrument removed"}


# NOTE: must stay above GET /instruments/{ticker} - otherwise "compare" would
# be matched as a {ticker} path value.
@app.get("/instruments/compare")
def compare_instruments(tickers: str):
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if len(ticker_list) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two tickers to compare")

    results = []
    for ticker in ticker_list:
        metadata = fetch_asset_metadata(ticker)
        if not metadata:
            continue
        metadata["live_price"] = get_live_price(ticker)
        results.append(metadata)

    if not results:
        raise HTTPException(status_code=404, detail="No valid tickers found")

    return {"instruments": results}


@app.get("/instruments/{ticker}")
def get_instrument_profile(ticker: str, db: Session = Depends(get_db)):
    instrument = crud.get_instrument_by_ticker(db, ticker)
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not registered")

    metadata = fetch_asset_metadata(ticker) or {}
    metadata.pop("ticker", None)

    return {
        "ticker": instrument.ticker,
        "type": instrument.type,
        "added_at": instrument.added_at,
        "live_price": get_live_price(ticker),
        **metadata
    }


@app.get("/instruments/{ticker}/history")
def get_instrument_history(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
    db: Session = Depends(get_db)
):
    if not crud.get_instrument_by_ticker(db, ticker):
        raise HTTPException(status_code=404, detail="Instrument not registered")

    return {
        "ticker": ticker.upper(),
        "period": period,
        "interval": interval,
        "history": get_price_history(ticker, period, interval)
    }
