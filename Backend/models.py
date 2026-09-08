from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from database import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True, nullable=False)
    type = Column(String, nullable=False)  # stock | etf | crypto | index
    added_at = Column(DateTime, default=datetime.utcnow)
