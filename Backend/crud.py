# Backend/crud.py
from sqlalchemy.orm import Session
import models
import schemas

# -------------------------------
# Instruments (registry)
# -------------------------------
def create_instrument(db: Session, instrument: schemas.InstrumentCreate):
    db_instrument = models.Instrument(
        ticker=instrument.ticker.upper(),
        type=instrument.type
    )
    db.add(db_instrument)
    db.commit()
    db.refresh(db_instrument)
    return db_instrument


def get_instruments(db: Session):
    return db.query(models.Instrument).all()


def get_instrument_by_ticker(db: Session, ticker: str):
    return db.query(models.Instrument).filter(models.Instrument.ticker == ticker.upper()).first()


def delete_instrument(db: Session, ticker: str):
    instrument = get_instrument_by_ticker(db, ticker)
    if not instrument:
        return False
    db.delete(instrument)
    db.commit()
    return True
