# Backend/crud.py
from sqlalchemy.orm import Session
import models
import schemas

# -------------------------------
# Transactions
# -------------------------------
def create_transaction(db: Session, transaction: schemas.TransactionCreate):
    db_transaction = models.Transaction(
        ticker=transaction.ticker.upper(),
        quantity=transaction.quantity,
        price=transaction.price,
        type=transaction.type.lower(),
        date=transaction.date
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


def get_transactions(db: Session):
    return db.query(models.Transaction).all()


def delete_transaction(db: Session, transaction_id: int):
    transaction = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id
    ).first()
    if not transaction:
        return False
    db.delete(transaction)
    db.commit()
    return True


# -------------------------------
# Assets
# -------------------------------
def create_asset(db: Session, asset: schemas.AssetCreate):
    db_asset = models.Asset(
        ticker=asset.ticker.upper(),
        name=asset.name,
        sector=asset.sector,
        industry=asset.industry,
        country=asset.country,
        market_cap=asset.market_cap,
        pe_ratio=asset.pe_ratio,
        beta=asset.beta,
        roe=asset.roe,
        dividend_yield=asset.dividend_yield
    )
    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)
    return db_asset


def get_assets(db: Session):
    return db.query(models.Asset).all()


def get_asset_by_ticker(db: Session, ticker: str):
    return db.query(models.Asset).filter(models.Asset.ticker == ticker.upper()).first()


# -------------------------------
# Positions (derived from Transactions)
# -------------------------------
def get_positions(db: Session):
    """
    Returns all positions (net quantity per ticker).
    """
    transactions = get_transactions(db)
    positions_dict = {}
    for t in transactions:
        ticker = t.ticker.upper()
        qty = t.quantity if t.type.lower() == "buy" else -t.quantity
        avg_price = t.price

        if ticker not in positions_dict:
            positions_dict[ticker] = {"quantity": 0, "total_cost": 0}

        positions_dict[ticker]["total_cost"] += qty * avg_price
        positions_dict[ticker]["quantity"] += qty

    positions_list = []
    for ticker, data in positions_dict.items():
        if data["quantity"] <= 0:
            continue
        avg_cost = data["total_cost"] / data["quantity"]
        positions_list.append({
            "ticker": ticker,
            "quantity": data["quantity"],
            "avg_cost": avg_cost
        })
    return positions_list