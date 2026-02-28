# Backend/main.py

from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
import crud
import schemas

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SmartMoney v0.2", version="0.2")

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------- TRANSACTIONS --------------------
@app.post("/transactions", response_model=schemas.Transaction)
def create_transaction(transaction: schemas.TransactionCreate, db: Session = Depends(get_db)):
    try:
        db_transaction = crud.create_transaction(db, transaction)
        return db_transaction
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/transactions", response_model=list[schemas.Transaction])
def get_transactions(db: Session = Depends(get_db)):
    return crud.get_transactions(db)


@app.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    success = crud.delete_transaction(db, transaction_id)
    if not success:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Transaction deleted successfully"}


# -------------------- POSITIONS --------------------
@app.get("/positions")
def get_positions(db: Session = Depends(get_db)):
    return crud.get_positions(db)


@app.get("/positions/{ticker}")
def get_position(ticker: str, db: Session = Depends(get_db)):
    position = crud.get_position(db, ticker)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    return position


# -------------------- ASSETS --------------------
@app.get("/assets")
def get_assets(db: Session = Depends(get_db)):
    from models import Asset
    return db.query(Asset).all()


@app.get("/assets/{ticker}")
def get_asset(ticker: str, db: Session = Depends(get_db)):
    from models import Asset
    asset = db.query(Asset).filter(Asset.ticker == ticker.upper()).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


# -------------------- ANALYTICS --------------------
@app.get("/portfolio/analytics")
def portfolio_analytics(db: Session = Depends(get_db)):
    from services.analytics import generate_portfolio_report
    report = generate_portfolio_report(db)
    return report