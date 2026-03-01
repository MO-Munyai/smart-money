# services/portfolio.py

from sqlalchemy.orm import Session
from models import Transaction, Position
from datetime import date, datetime
from sqlalchemy import func


def rebuild_positions_from_transactions(db: Session):
    """
    Rebuild all positions from the transactions table.
    Updates Position table and returns list of Position objects.
    """
    positions = {}

    # Get all transactions
    transactions = db.query(Transaction).order_by(Transaction.date).all()

    for t in transactions:
        ticker = t.ticker.upper()
        qty = t.quantity if t.type.lower() == "buy" else -t.quantity
        price = t.price

        if ticker not in positions:
            positions[ticker] = {"quantity": 0, "total_cost": 0}

        pos = positions[ticker]

        if qty > 0:  # buy
            pos["total_cost"] += qty * price
            pos["quantity"] += qty
        else:  # sell
            if pos["quantity"] + qty <= 0:
                # Sold all or more than we have
                pos["quantity"] = 0
                pos["total_cost"] = 0
            else:
                avg_cost = pos["total_cost"] / pos["quantity"]
                pos["total_cost"] += qty * avg_cost  # qty is negative
                pos["quantity"] += qty

    # Update Position table
    result = []
    for ticker, data in positions.items():
        quantity = data["quantity"]
        if quantity <= 0:
            continue
        avg_cost = data["total_cost"] / quantity if quantity > 0 else 0
        position = db.query(Position).filter(Position.ticker == ticker).first()
        if not position:
            position = Position(ticker=ticker, quantity=quantity, avg_cost=avg_cost)
            db.add(position)
        else:
            position.quantity = quantity
            position.avg_cost = avg_cost
        result.append(position)

    db.commit()
    return result


def get_positions(db: Session):
    """Return all current positions."""
    return db.query(Position).all()


def get_position(db: Session, ticker: str):
    """Return a single position by ticker."""
    return db.query(Position).filter(Position.ticker == ticker.upper()).first()


# -----------------------------
# Portfolio history support
# -----------------------------
def get_portfolio_history(db: Session):
    """
    Returns portfolio value snapshots for each transaction date.
    Output: list of dicts with 'date', 'total_invested', 'total_value'
    """
    # Get all unique dates from transactions
    dates = db.query(Transaction.date).distinct().order_by(Transaction.date).all()
    history = []

    for d_tuple in dates:
        txn_date = d_tuple[0]

        # Filter transactions up to this date
        transactions_up_to_date = db.query(Transaction).filter(Transaction.date <= txn_date).all()

        # Rebuild positions temporarily
        temp_positions = {}
        for t in transactions_up_to_date:
            ticker = t.ticker.upper()
            qty = t.quantity if t.type.lower() == "buy" else -t.quantity
            price = t.price
            if ticker not in temp_positions:
                temp_positions[ticker] = {"quantity": 0, "total_cost": 0}
            pos = temp_positions[ticker]
            if qty > 0:
                pos["total_cost"] += qty * price
                pos["quantity"] += qty
            else:
                if pos["quantity"] + qty <= 0:
                    pos["quantity"] = 0
                    pos["total_cost"] = 0
                else:
                    avg_cost = pos["total_cost"] / pos["quantity"]
                    pos["total_cost"] += qty * avg_cost
                    pos["quantity"] += qty

        total_invested = 0
        total_value = 0
        for ticker, data in temp_positions.items():
            quantity = data["quantity"]
            if quantity <= 0:
                continue
            avg_cost = data["total_cost"] / quantity
            total_invested += data["total_cost"]

            # Live price may not be available here, just use last transaction price
            total_value += quantity * avg_cost

        history.append({
            "date": txn_date.strftime("%Y-%m-%d"),
            "total_invested": total_invested,
            "total_value": total_value
        })

    return history