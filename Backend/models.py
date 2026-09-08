from sqlalchemy import Column, Integer, String, Float
from database import Base


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