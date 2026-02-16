from pydantic import BaseModel, Field
from datetime import date


class TransactionCreate(BaseModel):
    ticker: str = Field(..., example="AAPL")
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    type: str = Field(..., example="buy")
    date: date


class TransactionResponse(BaseModel):
    id: int
    ticker: str
    quantity: float
    price: float
    type: str
    date: date

    class Config:
        from_attributes = True