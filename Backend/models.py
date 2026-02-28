from sqlalchemy import Column, Integer, String, Float, Date
from database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    type = Column(String, nullable=False)  # buy or sell
    date = Column(Date, nullable=False)

class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True)
    ticker = Column(String, unique=True, index=True)
    name = Column(String)
    sector = Column(String)
    industry = Column(String)
    country = Column(String)
    market_cap = Column(Float)
    pe_ratio = Column(Float)
    beta = Column(Float)
    roe = Column(Float)
    dividend_yield = Column(Float)

