# Backend/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
import crud
from database import SessionLocal, engine
from services.market import fetch_asset_metadata
from services import portfolio
from services.analytics import generate_portfolio_report

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
@app.post("/transactions", response_model=schemas.TransactionBase)
def create_transaction(transaction: schemas.TransactionCreate, db: Session = Depends(get_db)):
    db_transaction = crud.create_transaction(db, transaction)
    # Rebuild positions after each transaction
    portfolio.rebuild_positions_from_transactions(db)
    return db_transaction


@app.get("/transactions", response_model=List[schemas.TransactionBase])
def get_transactions(db: Session = Depends(get_db)):
    return crud.get_transactions(db)


@app.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    success = crud.delete_transaction(db, transaction_id)
    if not success:
        raise HTTPException(status_code=404, detail="Transaction not found")
    # Rebuild positions after deletion
    portfolio.rebuild_positions_from_transactions(db)
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
# Portfolio Endpoints
# -------------------------------
@app.get("/portfolio/summary")
def portfolio_summary(db: Session = Depends(get_db)):
    """
    Returns live portfolio summary using positions rebuilt from transactions.
    """
    portfolio.rebuild_positions_from_transactions(db)
    positions = portfolio.get_positions(db)

    total_invested = sum(p.avg_cost * p.quantity for p in positions)
    total_value = sum(p.quantity * p.avg_cost for p in positions)  # temp; can replace with live prices
    total_gain_loss = total_value - total_invested

    positions_data = [
        {
            "ticker": p.ticker,
            "quantity": p.quantity,
            "avg_cost": p.avg_cost,
            "invested": p.avg_cost * p.quantity
        }
        for p in positions
    ]

    return {
        "total_invested": total_invested,
        "current_value": total_value,
        "total_gain_loss": total_gain_loss,
        "positions": positions_data
    }


@app.get("/portfolio/analytics")
def portfolio_analytics(db: Session = Depends(get_db)):
    """
    Returns full portfolio analytics:
    - sector & industry breakdown
    - weighted metrics (PE, Beta, ROE, Dividend Yield)
    - gain/loss per position
    """
    # Ensure positions are rebuilt
    portfolio.rebuild_positions_from_transactions(db)
    return generate_portfolio_report(db)