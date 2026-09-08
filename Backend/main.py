# Backend/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
import crud
from database import SessionLocal, engine
from services.market import get_live_price

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


@app.get("/instruments", response_model=List[schemas.Instrument])
def list_instruments(db: Session = Depends(get_db)):
    return crud.get_instruments(db)


@app.delete("/instruments/{ticker}")
def remove_instrument(ticker: str, db: Session = Depends(get_db)):
    if not crud.delete_instrument(db, ticker):
        raise HTTPException(status_code=404, detail="Instrument not found")
    return {"message": "Instrument removed"}
