# Backend/schemas.py
from pydantic import BaseModel
from typing import Optional

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
        from_attributes = True