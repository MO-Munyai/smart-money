# Backend/schemas.py
from pydantic import BaseModel, Field
from datetime import date
from typing import Optional

# -------------------------------
# Transaction Schemas
# -------------------------------
class TransactionBase(BaseModel):
    ticker: str = Field(..., example="AAPL")
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    type: str = Field(..., example="buy")  # buy or sell
    date: date

class TransactionCreate(TransactionBase):
    pass

class Transaction(TransactionBase):
    id: int

    class Config:
        orm_mode = True


# -------------------------------
# Position Schemas
# -------------------------------
class PositionBase(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float

class PositionCreate(PositionBase):
    pass

class Position(PositionBase):
    id: int

    class Config:
        orm_mode = True


# -------------------------------
# Asset Schemas
# -------------------------------
class AssetBase(BaseModel):
    ticker: str
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    beta: Optional[float] = None
    roe: Optional[float] = None
    dividend_yield: Optional[float] = None

class AssetCreate(AssetBase):
    pass

class Asset(AssetBase):
    id: int

    class Config:
        orm_mode = True