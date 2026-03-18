import logging
from datetime import date

import yfinance as yf
from sqlalchemy.orm import Session

from app.models import Fundamentals
from app.data.session import get_yf_session

logger = logging.getLogger(__name__)

NSE_SUFFIX = ".NS"


def _safe_get(info: dict, key: str, default=None):
    val = info.get(key, default)
    if val is None or val == "":
        return default
    return val


def _as_pct(val, already_pct_threshold=5.0):
    """Convert a value that might be fractional (0.25) or already percentage (25.0)."""
    if val is None:
        return None
    if abs(val) < already_pct_threshold:
        return val * 100
    return val


def _r2(val):
    """Round to 2 decimal places, pass through None."""
    return round(val, 2) if val is not None else None


def fetch_fundamentals_for_symbol(symbol: str, db: Session | None = None) -> dict | None:
    """Fetch fundamental data from Yahoo Finance and optionally persist."""
    yf_sym = symbol + NSE_SUFFIX if not symbol.endswith(NSE_SUFFIX) else symbol
    clean = symbol.replace(NSE_SUFFIX, "")
    try:
        session = get_yf_session()
        ticker = yf.Ticker(yf_sym, session=session)
        info = ticker.info or {}

        if not info.get("regularMarketPrice"):
            logger.warning("No market data for %s", clean)
            return None

        market_cap_cr = (_safe_get(info, "marketCap", 0) or 0) / 1e7

        pe = _safe_get(info, "trailingPE")
        pb = _safe_get(info, "priceToBook")
        eps = _safe_get(info, "trailingEps")

        roe = _safe_get(info, "returnOnEquity")
        if roe is not None:
            roe = _as_pct(roe)

        # Fallback: compute ROE from net income / total equity if yfinance doesn't provide it
        if roe is None:
            try:
                bs = ticker.balance_sheet
                inc = ticker.income_stmt
                if bs is not None and not bs.empty and inc is not None and not inc.empty:
                    equity = None
                    for col_name in ["Stockholders Equity", "Total Stockholder Equity",
                                     "StockholdersEquity", "Stockholders' Equity"]:
                        if col_name in bs.index:
                            equity = float(bs.loc[col_name].iloc[0])
                            break
                    net_income = None
                    for col_name in ["Net Income", "NetIncome", "Net Income Common Stockholders"]:
                        if col_name in inc.index:
                            net_income = float(inc.loc[col_name].iloc[0])
                            break
                    if equity and equity > 0 and net_income is not None:
                        roe = (net_income / equity) * 100
            except Exception:
                pass

        # yfinance debtToEquity is already a ratio expressed as a percentage
        # e.g. 6.257 means 6.257% which is a 0.06257 D/E ratio.
        # Values like 35.6 mean 35.6% = 0.356 D/E ratio.
        debt_equity = _safe_get(info, "debtToEquity")
        if debt_equity is not None:
            debt_equity = debt_equity / 100.0

        revenue_growth = _safe_get(info, "revenueGrowth")
        if revenue_growth is not None:
            revenue_growth = _as_pct(revenue_growth)

        earnings_growth = _safe_get(info, "earningsGrowth")
        if earnings_growth is not None:
            earnings_growth = _as_pct(earnings_growth)

        dividend_yield = _safe_get(info, "dividendYield")
        if dividend_yield is not None:
            dividend_yield = _as_pct(dividend_yield, already_pct_threshold=1.0)

        peg = _safe_get(info, "pegRatio")
        if peg is None and pe is not None and pe > 0 and earnings_growth is not None and earnings_growth > 0:
            peg = pe / earnings_growth

        forward_pe = _safe_get(info, "forwardPE")

        earnings_yield = None
        if pe and pe > 0:
            earnings_yield = (1.0 / pe) * 100

        promoter_holding = _safe_get(info, "heldPercentInsiders")
        if promoter_holding is not None:
            promoter_holding = _as_pct(promoter_holding)
        if promoter_holding is None:
            promoter_holding = 50.0

        fund = {
            "symbol": clean,
            "as_of_date": date.today(),
            "market_cap_cr": _r2(market_cap_cr),
            "pe_ratio": _r2(pe),
            "pb_ratio": _r2(pb),
            "roe": _r2(roe),
            "roce": _r2(roe),
            "debt_equity": _r2(debt_equity),
            "promoter_holding": _r2(promoter_holding),
            "promoter_pledge": 0.0,
            "revenue_growth_3yr": _r2(revenue_growth),
            "profit_growth_3yr": _r2(earnings_growth),
            "eps": _r2(eps),
            "dividend_yield": _r2(dividend_yield),
            "free_cash_flow_positive_years": 2,
            "peg_ratio": _r2(peg),
            "earnings_yield": _r2(earnings_yield),
            "pe_5yr_median": _r2(pe),
        }

        if db is not None:
            _persist_fundamentals(db, fund)

        return fund

    except Exception as e:
        logger.exception("Failed to fetch fundamentals for %s: %s", clean, e)
        return None


def _persist_fundamentals(db: Session, fund: dict) -> None:
    existing = (
        db.query(Fundamentals)
        .filter(
            Fundamentals.symbol == fund["symbol"],
            Fundamentals.as_of_date == fund["as_of_date"],
        )
        .first()
    )
    if existing:
        for k, v in fund.items():
            if k not in ("symbol", "as_of_date") and v is not None:
                setattr(existing, k, v)
    else:
        db.add(Fundamentals(**fund))
    db.commit()


def fetch_fundamentals_batch(symbols: list[str], db: Session) -> int:
    """Fetch fundamentals for multiple symbols. Returns count of successful fetches."""
    success = 0
    for sym in symbols:
        result = fetch_fundamentals_for_symbol(sym, db=db)
        if result is not None:
            success += 1
    logger.info("Fetched fundamentals for %d/%d symbols", success, len(symbols))
    return success
