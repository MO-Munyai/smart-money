# crud.py

from sqlalchemy.orm import Session
from models import Transaction, Position, Asset
from schemas import TransactionCreate
from services.portfolio import rebuild_positions_from_transactions
from services.market import fetch_asset_metadata  # new function to get asset metadata


def create_transaction(db: Session, transaction: TransactionCreate):
    # --- Step 1: Insert transaction ---
    db_transaction = Transaction(
        ticker=transaction.ticker.upper(),
        quantity=transaction.quantity,
        price=transaction.price,
        type=transaction.type.lower(),  # "buy" or "sell"
        date=transaction.date
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    # --- Step 2: Ensure asset metadata exists ---
    ticker = transaction.ticker.upper()
    asset = db.query(Asset).filter(Asset.ticker == ticker).first()
    if not asset:
        metadata = fetch_asset_metadata(ticker)
        if metadata:
            asset = Asset(
                ticker=ticker,
                name=metadata.get("name"),
                sector=metadata.get("sector"),
                industry=metadata.get("industry"),
                country=metadata.get("country"),
                market_cap=metadata.get("market_cap"),
                pe_ratio=metadata.get("pe_ratio"),
                beta=metadata.get("beta"),
                roe=metadata.get("roe"),
                dividend_yield=metadata.get("dividend_yield")
            )
            db.add(asset)
            db.commit()
            db.refresh(asset)

    # --- Step 3: Update positions ---
    rebuild_positions_from_transactions(db)

    return db_transaction


def get_transactions(db: Session):
    return db.query(Transaction).all()


def delete_transaction(db: Session, transaction_id: int):
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id
    ).first()

    if not transaction:
        return False

    db.delete(transaction)
    db.commit()

    # Rebuild positions after deletion
    rebuild_positions_from_transactions(db)
    return True


def get_positions(db: Session):
    from services.portfolio import get_positions as portfolio_get_positions
    return portfolio_get_positions(db)


def get_position(db: Session, ticker: str):
    from services.portfolio import get_position as portfolio_get_position
    return portfolio_get_position(db, ticker)