# Backend/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
import crud
from database import SessionLocal, engine
from services.market import fetch_asset_metadata

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
# Assets Endpoints
# -------------------------------
@app.post("/assets", response_model=schemas.Asset)
def create_asset(asset: schemas.AssetCreate, db: Session = Depends(get_db)):
    db_asset = crud.get_asset_by_ticker(db, asset.ticker)
    if db_asset:
        raise HTTPException(status_code=400, detail="Asset already exists")
    return crud.create_asset(db, asset)


@app.get("/assets", response_model=List[schemas.Asset])
def get_assets(db: Session = Depends(get_db)):
    return crud.get_assets(db)


@app.get("/assets/fetch/{ticker}", response_model=schemas.Asset)
def fetch_asset(ticker: str, db: Session = Depends(get_db)):
    metadata = fetch_asset_metadata(ticker)
    if not metadata:
        raise HTTPException(status_code=404, detail="Ticker metadata not found")
    # Save to DB if not exists
    db_asset = crud.get_asset_by_ticker(db, ticker)
    if not db_asset:
        db_asset = crud.create_asset(db, schemas.AssetCreate(**metadata))
    return db_asset
