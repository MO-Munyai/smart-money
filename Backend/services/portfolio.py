# services/portfolio.py

from sqlalchemy.orm import Session
from models import Transaction, Position
from datetime import date


def rebuild_positions_from_transactions(db: Session):
    """
    Rebuild all positions from the transactions table.
    Returns a list of position objects (Position instances).
    """
    positions = {}

    # Get all transactions
    transactions = db.query(Transaction).all()

    for t in transactions:
        ticker = t.ticker.upper()
        qty = t.quantity if t.type.lower() == "buy" else -t.quantity
        price = t.price

        if ticker not in positions:
            positions[ticker] = {
                "quantity": 0,
                "total_cost": 0  # sum(qty * price)
            }

        pos = positions[ticker]
        # Update quantity and total_cost
        if qty > 0:  # buy
            pos["total_cost"] += qty * price
            pos["quantity"] += qty
        else:  # sell
            # Avoid negative quantity and adjust total_cost proportionally
            if pos["quantity"] + qty <= 0:
                # Sold all or more than we have
                pos["quantity"] = 0
                pos["total_cost"] = 0
            else:
                avg_cost = pos["total_cost"] / pos["quantity"]
                pos["total_cost"] += qty * avg_cost  # qty is negative
                pos["quantity"] += qty

    # Build Position instances
    result = []
    for ticker, data in positions.items():
        quantity = data["quantity"]
        if quantity <= 0:
            continue

        avg_cost = data["total_cost"] / quantity if quantity > 0 else 0

        # Check if position exists in DB
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
    """
    Return all current positions.
    """
    return db.query(Position).all()


def get_position(db: Session, ticker: str):
    """
    Return a single position by ticker.
    """
    return db.query(Position).filter(Position.ticker == ticker.upper()).first()