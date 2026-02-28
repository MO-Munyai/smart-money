# Backend/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
import crud
from database import SessionLocal, engine
from services.market import calculate_portfolio_summary, fetch_asset_metadata

# Create DB tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="SmartMoney v0.2")

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------
# Transactions Endpoints
# -------------------------------
@app.post("/transactions", response_model=schemas.Transaction)
def create_transaction(transaction: schemas.TransactionCreate, db: Session = Depends(get_db)):
    return crud.create_transaction(db, transaction)


@app.get("/transactions", response_model=List[schemas.Transaction])
def get_transactions(db: Session = Depends(get_db)):
    return crud.get_transactions(db)


@app.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    success = crud.delete_transaction(db, transaction_id)
    if not success:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Transaction deleted successfully"}


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


# -------------------------------
# Portfolio Analytics
# -------------------------------
@app.get("/portfolio/summary")
def portfolio_summary(db: Session = Depends(get_db)):
    transactions = crud.get_transactions(db)
    return calculate_portfolio_summary(transactions)


@app.get("/portfolio/analytics")
def portfolio_analytics(db: Session = Depends(get_db)):
    from services.analytics import generate_portfolio_report
    return generate_portfolio_report(db)