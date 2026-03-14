import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import SessionLocal
from app.data.fetcher import (
    sync_stock_list,
    fetch_price_history,
    load_price_history_from_db,
    fetch_benchmark,
)
from app.data.fundamentals import fetch_fundamentals_batch
from app.screener.fundamental import screen_stocks
from app.screener.universe import update_universe, get_universe
from app.signals.technical import compute_technical_score
from app.signals.momentum import compute_momentum_score
from app.signals.valuation import compute_valuation_score
from app.signals.composite import compute_composite_signal
from app.models import Signal, Stock, Fundamentals, SignalType
from app.alerts.telegram import send_telegram_alert
from app.alerts.email import send_email_alert

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Kolkata")


def run_daily_scan():
    """Full pipeline: fetch data -> screen -> score -> alert."""
    logger.info("=== Starting daily scan at %s ===", datetime.utcnow().isoformat())
    db = SessionLocal()

    try:
        # Step 1: Sync stock master list
        logger.info("Step 1/6: Syncing stock list")
        sync_stock_list(db)

        all_symbols = [r.symbol for r in db.query(Stock.symbol).all()]
        logger.info("Total stocks in DB: %d", len(all_symbols))

        # Step 2: Fetch fundamentals.
        # Fetching all 500 is slow (~2-3s per stock). We batch-fetch a manageable
        # subset first. On subsequent runs the DB already has data so the screener
        # can work with existing fundamentals.
        existing_fund_count = db.query(Fundamentals.symbol).distinct().count()
        if existing_fund_count < 50:
            # First run — use the curated seed list for fast bootstrapping
            from app.data.fetcher import _seed_stock_list
            seed_symbols = [s["symbol"] for s in _seed_stock_list()]
            targets = seed_symbols
            logger.info(
                "Step 2/6: First run — fetching fundamentals for %d seed stocks",
                len(targets),
            )
        else:
            # Incremental: only re-fetch for stocks already in universe + a sample of new ones
            universe_syms = get_universe(db)
            # Add some stocks not yet in fundamentals table
            known = set(
                r[0] for r in db.query(Fundamentals.symbol).distinct().all()
            )
            new_batch = [s for s in all_symbols if s not in known][:30]
            targets = list(set(universe_syms + new_batch))
            logger.info(
                "Step 2/6: Incremental — fetching fundamentals for %d stocks "
                "(%d universe + %d new)",
                len(targets),
                len(universe_syms),
                len(new_batch),
            )

        success = fetch_fundamentals_batch(targets, db)
        logger.info("Fundamentals fetched: %d/%d succeeded", success, len(targets))

        # Step 3: Run fundamental screener
        logger.info("Step 3/6: Running fundamental screener")
        passing = screen_stocks(db)
        update_universe(db, passing)
        logger.info("Screener passed %d stocks", len(passing))

        universe = get_universe(db)
        if not universe:
            logger.warning("No stocks in universe after screening — check data / filters")
            return

        # Step 4: Fetch price history for universe stocks
        logger.info("Step 4/6: Fetching price history for %d stocks", len(universe))
        for i, sym in enumerate(universe):
            fetch_price_history(sym, period="2y", db=db)
            if (i + 1) % 10 == 0:
                logger.info("  prices: %d/%d done", i + 1, len(universe))

        benchmark_df = fetch_benchmark(period="2y")

        # Step 5: Compute signals
        logger.info("Step 5/6: Computing signals for %d stocks", len(universe))
        now = datetime.utcnow()
        new_signals = []

        for sym in universe:
            price_df = load_price_history_from_db(db, sym)
            fund_row = (
                db.query(Fundamentals)
                .filter(Fundamentals.symbol == sym)
                .order_by(Fundamentals.as_of_date.desc())
                .first()
            )

            tech_score, tech_details = compute_technical_score(price_df)
            mom_score, mom_details = compute_momentum_score(price_df, benchmark_df)

            fund_dict = {}
            if fund_row:
                fund_dict = {
                    "pe_ratio": fund_row.pe_ratio,
                    "pb_ratio": fund_row.pb_ratio,
                    "peg_ratio": fund_row.peg_ratio,
                    "earnings_yield": fund_row.earnings_yield,
                    "dividend_yield": fund_row.dividend_yield,
                    "pe_5yr_median": fund_row.pe_5yr_median,
                }
            val_score, val_details = compute_valuation_score(fund_dict)

            from app.screener.fundamental import _fundamental_quality_score

            fund_score = _fundamental_quality_score(fund_row) if fund_row else 0.0

            composite, signal_type, reasoning, sub_scores = compute_composite_signal(
                fundamental_score=fund_score,
                technical_score=tech_score,
                momentum_score=mom_score,
                valuation_score=val_score,
                fundamental_pass=True,
            )

            signal = Signal(
                symbol=sym,
                generated_at=now,
                fundamental_score=fund_score,
                technical_score=tech_score,
                momentum_score=mom_score,
                valuation_score=val_score,
                composite_score=composite,
                signal_type=signal_type,
                reasoning=reasoning,
                rsi=tech_details.get("rsi"),
                macd_signal=tech_details.get("macd_signal"),
                ma_crossover=tech_details.get("ma_crossover"),
                volume_spike=tech_details.get("volume_spike", False),
                relative_strength_6m=mom_details.get("relative_strength_6m"),
                near_52w_high=mom_details.get("near_52w_high", False),
                near_52w_low=mom_details.get("near_52w_low", False),
            )
            db.add(signal)
            new_signals.append(signal)

        db.commit()
        logger.info("Generated %d signals", len(new_signals))

        # Step 6: Send alerts for actionable signals
        logger.info("Step 6/6: Sending alerts for actionable signals")
        for sig in new_signals:
            if sig.signal_type in (SignalType.STRONG_BUY, SignalType.EXIT):
                _send_alert(sig)

        logger.info("=== Daily scan complete: %d signals generated ===", len(new_signals))

    except Exception as e:
        logger.exception("Daily scan failed: %s", e)
    finally:
        db.close()


def _send_alert(signal: Signal):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            send_telegram_alert(
                signal.symbol,
                signal.signal_type.value,
                signal.composite_score,
                signal.reasoning or "",
            )
        )
        loop.close()
    except Exception:
        logger.exception("Telegram alert failed for %s", signal.symbol)

    try:
        send_email_alert(
            signal.symbol,
            signal.signal_type.value,
            signal.composite_score,
            signal.reasoning or "",
        )
    except Exception:
        logger.exception("Email alert failed for %s", signal.symbol)


def start_scheduler():
    scheduler.add_job(
        run_daily_scan,
        "cron",
        hour=settings.scan_hour,
        minute=settings.scan_minute,
        id="daily_scan",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started — daily scan at %02d:%02d IST",
        settings.scan_hour,
        settings.scan_minute,
    )


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
