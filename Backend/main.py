# Backend/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
import crud
from database import SessionLocal, engine
from services.market import get_live_price, get_live_prices, get_price_history, fetch_asset_metadata

# Create DB tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="SmartMoney v0.3")

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
