from pydantic_settings import BaseSettings
from pathlib import Path


class ScreenerThresholds(BaseSettings):
    min_market_cap_cr: float = 500
    max_market_cap_cr: float = 150_000
    min_roe: float = 12.0
    min_roce: float = 12.0
    max_debt_equity: float = 1.5
    min_promoter_holding: float = 25.0
    max_promoter_pledge: float = 20.0
    min_revenue_growth_3yr: float = 5.0
    min_profit_growth_3yr: float = 5.0
    require_positive_fcf_years: int = 2


class SignalWeights(BaseSettings):
    fundamental: float = 0.30
    technical: float = 0.25
    momentum: float = 0.20
    valuation: float = 0.25


class SignalThresholds(BaseSettings):
    strong_buy_min: float = 80.0
    buy_min: float = 60.0
    hold_min: float = 40.0

    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    volume_spike_multiplier: float = 2.0
    pe_undervalued_ratio: float = 0.8
    max_peg: float = 1.0


class Settings(BaseSettings):
    database_url: str = "sqlite:///./stock_signals.db"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    email_host: str = "smtp.gmail.com"
    email_port: int = 587
    email_user: str = ""
    email_password: str = ""
    email_recipients: str = ""

    scan_hour: int = 18
    scan_minute: int = 30

    screener: ScreenerThresholds = ScreenerThresholds()
    weights: SignalWeights = SignalWeights()
    thresholds: SignalThresholds = SignalThresholds()

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
