from sqlalchemy.orm import Session
import models
import schemas


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