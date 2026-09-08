# Backend/schemas.py
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

# -------------------------------
# Instrument Schemas
# -------------------------------
class InstrumentType(str, Enum):
    stock = "stock"
    etf = "etf"
    crypto = "crypto"
    index = "index"

class InstrumentBase(BaseModel):
    ticker: str
    type: InstrumentType

class InstrumentCreate(InstrumentBase):
    pass

class Instrument(InstrumentBase):
    id: int
    added_at: datetime

    class Config:
        from_attributes = True
