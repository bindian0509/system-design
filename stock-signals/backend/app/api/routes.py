import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Stock,
    Signal,
    Fundamentals,
    AlertLog,
    WatchlistItem,
    SignalType,
    StockResponse,
    SignalResponse,
    FundamentalsResponse,
    AlertLogResponse,
    DashboardSummary,
)
from app.screener.universe import get_universe, add_to_watchlist, get_watchlist
from app.data.fetcher import load_price_history_from_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/dashboard", response_model=DashboardSummary)
def get_dashboard(db: Session = Depends(get_db)):
    universe_count = db.query(Stock).filter(Stock.is_in_universe == True).count()

    from sqlalchemy import func

    latest_date_subq = db.query(func.max(Signal.generated_at)).scalar()

    strong_buys = 0
    buys = 0
    holds = 0
    exits = 0

    if latest_date_subq:
        signals = (
            db.query(Signal)
            .filter(Signal.generated_at == latest_date_subq)
            .all()
        )
        for s in signals:
            if s.signal_type == SignalType.STRONG_BUY:
                strong_buys += 1
            elif s.signal_type == SignalType.BUY:
                buys += 1
            elif s.signal_type == SignalType.HOLD:
                holds += 1
            elif s.signal_type == SignalType.EXIT:
                exits += 1

    return DashboardSummary(
        total_universe=universe_count,
        strong_buys=strong_buys,
        buys=buys,
        holds=holds,
        exits=exits,
        last_scan=latest_date_subq,
    )


@router.get("/signals", response_model=list[SignalResponse])
def get_latest_signals(
    signal_type: SignalType | None = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Signal).order_by(Signal.generated_at.desc())
    if signal_type:
        q = q.filter(Signal.signal_type == signal_type)
    return q.limit(limit).all()


@router.get("/signals/{symbol}", response_model=list[SignalResponse])
def get_stock_signals(
    symbol: str,
    limit: int = Query(default=30, le=100),
    db: Session = Depends(get_db),
):
    signals = (
        db.query(Signal)
        .filter(Signal.symbol == symbol.upper())
        .order_by(Signal.generated_at.desc())
        .limit(limit)
        .all()
    )
    if not signals:
        raise HTTPException(404, f"No signals found for {symbol}")
    return signals


@router.get("/stocks", response_model=list[StockResponse])
def get_stocks(
    universe_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    q = db.query(Stock)
    if universe_only:
        q = q.filter(Stock.is_in_universe == True)
    return q.order_by(Stock.symbol).all()


@router.get("/stocks/{symbol}")
def get_stock_detail(symbol: str, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if not stock:
        raise HTTPException(404, f"Stock {symbol} not found")

    fund = (
        db.query(Fundamentals)
        .filter(Fundamentals.symbol == symbol.upper())
        .order_by(Fundamentals.as_of_date.desc())
        .first()
    )

    latest_signal = (
        db.query(Signal)
        .filter(Signal.symbol == symbol.upper())
        .order_by(Signal.generated_at.desc())
        .first()
    )

    return {
        "stock": StockResponse.model_validate(stock),
        "fundamentals": FundamentalsResponse.model_validate(fund) if fund else None,
        "latest_signal": SignalResponse.model_validate(latest_signal)
            if latest_signal
            else None,
    }


@router.get("/stocks/{symbol}/prices")
def get_stock_prices(
    symbol: str,
    limit: int = Query(default=365, le=1000),
    db: Session = Depends(get_db),
):
    df = load_price_history_from_db(db, symbol.upper())
    if df.empty:
        raise HTTPException(404, f"No price data for {symbol}")
    df = df.tail(limit)
    return df.to_dict(orient="records")


@router.get("/fundamentals/{symbol}", response_model=FundamentalsResponse)
def get_fundamentals(symbol: str, db: Session = Depends(get_db)):
    fund = (
        db.query(Fundamentals)
        .filter(Fundamentals.symbol == symbol.upper())
        .order_by(Fundamentals.as_of_date.desc())
        .first()
    )
    if not fund:
        raise HTTPException(404, f"No fundamentals for {symbol}")
    return fund


@router.get("/screener")
def get_screener_results(db: Session = Depends(get_db)):
    """Returns universe stocks with their latest signals and fundamentals."""
    universe_symbols = get_universe(db)
    results = []
    for sym in universe_symbols:
        stock = db.query(Stock).filter(Stock.symbol == sym).first()
        fund = (
            db.query(Fundamentals)
            .filter(Fundamentals.symbol == sym)
            .order_by(Fundamentals.as_of_date.desc())
            .first()
        )
        signal = (
            db.query(Signal)
            .filter(Signal.symbol == sym)
            .order_by(Signal.generated_at.desc())
            .first()
        )
        results.append(
            {
                "symbol": sym,
                "name": stock.name if stock else sym,
                "sector": stock.sector if stock else None,
                "market_cap_cr": fund.market_cap_cr if fund else None,
                "pe_ratio": fund.pe_ratio if fund else None,
                "roe": fund.roe if fund else None,
                "composite_score": signal.composite_score if signal else None,
                "signal_type": signal.signal_type.value if signal else None,
            }
        )
    results.sort(key=lambda x: x.get("composite_score") or 0, reverse=True)
    return results


@router.get("/alerts", response_model=list[AlertLogResponse])
def get_alert_history(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    return (
        db.query(AlertLog)
        .order_by(AlertLog.sent_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/watchlist")
def get_watchlist_items(db: Session = Depends(get_db)):
    items = get_watchlist(db)
    enriched = []
    for item in items:
        signal = (
            db.query(Signal)
            .filter(Signal.symbol == item["symbol"])
            .order_by(Signal.generated_at.desc())
            .first()
        )
        enriched.append(
            {
                **item,
                "composite_score": signal.composite_score if signal else None,
                "signal_type": signal.signal_type.value if signal else None,
            }
        )
    return enriched


@router.post("/watchlist/{symbol}")
def add_watchlist_item(
    symbol: str,
    notes: str = Query(default=None),
    db: Session = Depends(get_db),
):
    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if not stock:
        raise HTTPException(404, f"Stock {symbol} not found in database")
    add_to_watchlist(db, symbol.upper(), notes)
    return {"status": "added", "symbol": symbol.upper()}


@router.delete("/watchlist/{symbol}")
def remove_watchlist_item(symbol: str, db: Session = Depends(get_db)):
    item = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.symbol == symbol.upper())
        .first()
    )
    if not item:
        raise HTTPException(404, f"{symbol} not in watchlist")
    db.delete(item)
    db.commit()
    return {"status": "removed", "symbol": symbol.upper()}


@router.post("/scan/trigger")
def trigger_manual_scan(db: Session = Depends(get_db)):
    """Trigger an immediate signal scan (normally runs on schedule)."""
    from app.scheduler import run_daily_scan

    try:
        run_daily_scan()
        return {"status": "scan_triggered", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.exception("Manual scan failed")
        raise HTTPException(500, f"Scan failed: {str(e)}")
