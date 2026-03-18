from datetime import date, datetime
from enum import Enum as PyEnum

from pydantic import BaseModel, model_validator
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    DateTime,
    Boolean,
    Enum,
    Text,
    UniqueConstraint,
    Index,
)

from app.database import Base


class SignalType(str, PyEnum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    EXIT = "EXIT"


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    sector = Column(String(100))
    industry = Column(String(100))
    market_cap_cr = Column(Float)
    is_in_universe = Column(Boolean, default=False)
    last_updated = Column(DateTime, default=datetime.utcnow)


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (
        UniqueConstraint("symbol", "trade_date", name="uq_price_symbol_date"),
        Index("ix_price_symbol_date", "symbol", "trade_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    trade_date = Column(Date, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    delivery_volume = Column(Float, nullable=True)


class Fundamentals(Base):
    __tablename__ = "fundamentals"
    __table_args__ = (
        UniqueConstraint("symbol", "as_of_date", name="uq_fund_symbol_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    as_of_date = Column(Date, nullable=False)
    market_cap_cr = Column(Float)
    pe_ratio = Column(Float)
    pb_ratio = Column(Float)
    roe = Column(Float)
    roce = Column(Float)
    debt_equity = Column(Float)
    promoter_holding = Column(Float)
    promoter_pledge = Column(Float)
    revenue_growth_3yr = Column(Float)
    profit_growth_3yr = Column(Float)
    eps = Column(Float)
    dividend_yield = Column(Float)
    free_cash_flow_positive_years = Column(Integer)
    peg_ratio = Column(Float, nullable=True)
    earnings_yield = Column(Float, nullable=True)
    pe_5yr_median = Column(Float, nullable=True)


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        UniqueConstraint("symbol", "generated_at", name="uq_signal_symbol_date"),
        Index("ix_signal_date", "generated_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    fundamental_score = Column(Float)
    technical_score = Column(Float)
    momentum_score = Column(Float)
    valuation_score = Column(Float)
    composite_score = Column(Float)
    signal_type = Column(Enum(SignalType), nullable=False)
    reasoning = Column(Text)

    rsi = Column(Float)
    macd_signal = Column(String(10))
    ma_crossover = Column(String(20))
    volume_spike = Column(Boolean, default=False)
    relative_strength_6m = Column(Float)
    near_52w_high = Column(Boolean, default=False)
    near_52w_low = Column(Boolean, default=False)


class AlertLog(Base):
    __tablename__ = "alert_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    signal_type = Column(Enum(SignalType), nullable=False)
    channel = Column(String(20))
    message = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)
    success = Column(Boolean, default=True)


class WatchlistItem(Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("symbol", name="uq_watchlist_symbol"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)


# --- Pydantic response schemas ---


def _round_floats(data: dict, decimals: int = 2) -> dict:
    for k, v in data.items():
        if isinstance(v, float):
            data[k] = round(v, decimals)
    return data


class RoundedModel(BaseModel):
    """Base model that rounds all float fields to 2 decimal places."""

    @model_validator(mode="after")
    def round_all_floats(self):
        for field_name in self.model_fields:
            val = getattr(self, field_name)
            if isinstance(val, float):
                setattr(self, field_name, round(val, 2))
        return self


class StockResponse(RoundedModel):
    symbol: str
    name: str
    sector: str | None
    industry: str | None
    market_cap_cr: float | None
    is_in_universe: bool

    model_config = {"from_attributes": True}


class SignalResponse(RoundedModel):
    symbol: str
    generated_at: datetime
    fundamental_score: float | None
    technical_score: float | None
    momentum_score: float | None
    valuation_score: float | None
    composite_score: float | None
    signal_type: SignalType
    reasoning: str | None
    rsi: float | None
    macd_signal: str | None
    ma_crossover: str | None
    volume_spike: bool | None
    relative_strength_6m: float | None
    near_52w_high: bool | None
    near_52w_low: bool | None

    model_config = {"from_attributes": True}


class FundamentalsResponse(RoundedModel):
    symbol: str
    as_of_date: date
    market_cap_cr: float | None
    pe_ratio: float | None
    pb_ratio: float | None
    roe: float | None
    roce: float | None
    debt_equity: float | None
    promoter_holding: float | None
    promoter_pledge: float | None
    revenue_growth_3yr: float | None
    profit_growth_3yr: float | None
    peg_ratio: float | None

    model_config = {"from_attributes": True}


class AlertLogResponse(BaseModel):
    symbol: str
    signal_type: SignalType
    channel: str | None
    message: str | None
    sent_at: datetime
    success: bool

    model_config = {"from_attributes": True}


class DashboardSummary(BaseModel):
    total_universe: int
    strong_buys: int
    buys: int
    holds: int
    exits: int
    last_scan: datetime | None
