from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal, engine
import models
import schemas
import crud
from services import market

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Personal Stock Portfolio API")


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Stock Portfolio API is running."}


# Create transaction
@app.post("/transactions", response_model=schemas.TransactionResponse)
def create_transaction(
    transaction: schemas.TransactionCreate,
    db: Session = Depends(get_db)
):
    return crud.create_transaction(db=db, transaction=transaction)


# Get all transactions
@app.get("/transactions", response_model=List[schemas.TransactionResponse])
def get_transactions(db: Session = Depends(get_db)):
    return crud.get_transactions(db=db)


# Delete transaction
@app.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    deleted = crud.delete_transaction(db=db, transaction_id=transaction_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Transaction deleted successfully"}


# Get live price
@app.get("/price/{ticker}")
def get_price(ticker: str):
    price = market.get_live_price(ticker)
    if price is None:
        raise HTTPException(status_code=404, detail="Ticker not found")
    return {"ticker": ticker.upper(), "price": price}


# Portfolio summary
@app.get("/portfolio")
def get_portfolio(db: Session = Depends(get_db)):
    transactions = crud.get_transactions(db=db)
    summary = market.calculate_portfolio_summary(transactions)
    return summary