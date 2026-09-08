# Backend/crud.py
from sqlalchemy.orm import Session
import models
import schemas

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