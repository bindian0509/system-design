import asyncio
import logging
from datetime import datetime, date

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

FUNDAMENTALS_BATCH_SIZE = 50


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

        # Step 2: Fetch fundamentals — progressively expand coverage
        known_symbols = set(
            r[0] for r in db.query(Fundamentals.symbol).distinct().all()
        )
        universe_syms = get_universe(db)

        # Always re-fetch current universe to keep data fresh
        refresh_targets = list(universe_syms)

        # Add new stocks we haven't fetched yet, expanding coverage each run
        unseen = [s for s in all_symbols if s not in known_symbols]
        new_batch = unseen[:FUNDAMENTALS_BATCH_SIZE]

        targets = list(set(refresh_targets + new_batch))
        logger.info(
            "Step 2/6: Fetching fundamentals for %d stocks "
            "(%d universe refresh + %d new, %d/%d total coverage)",
            len(targets),
            len(refresh_targets),
            len(new_batch),
            len(known_symbols),
            len(all_symbols),
        )

        success = fetch_fundamentals_batch(targets, db)
        logger.info("Fundamentals fetched: %d/%d succeeded", success, len(targets))

        # Step 3: Run fundamental screener across ALL stocks with fundamentals
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

        # Step 5: Compute signals — delete today's old signals first to avoid duplicates
        logger.info("Step 5/6: Computing signals for %d stocks", len(universe))
        today = date.today()
        deleted = (
            db.query(Signal)
            .filter(Signal.generated_at >= datetime(today.year, today.month, today.day))
            .delete(synchronize_session=False)
        )
        if deleted:
            db.commit()
            logger.info("Cleared %d stale signals from today", deleted)

        now = datetime.utcnow()
        new_signals = []
        prev_signals = _load_previous_signals(db, universe)

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

        # Step 6: Send alerts only for signal changes (new entries or state transitions)
        logger.info("Step 6/6: Checking for alertable signal changes")
        alert_count = 0
        for sig in new_signals:
            prev = prev_signals.get(sig.symbol)
            should_alert = False

            if prev is None:
                # New stock in universe — alert if actionable
                should_alert = sig.signal_type in (SignalType.STRONG_BUY, SignalType.EXIT)
            elif prev != sig.signal_type.value:
                # Signal changed from previous scan
                should_alert = sig.signal_type in (SignalType.STRONG_BUY, SignalType.EXIT)

            if should_alert:
                _send_alert(sig)
                alert_count += 1

        logger.info(
            "=== Daily scan complete: %d signals, %d alerts sent ===",
            len(new_signals),
            alert_count,
        )

    except Exception as e:
        logger.exception("Daily scan failed: %s", e)
    finally:
        db.close()


def _load_previous_signals(db, symbols: list[str]) -> dict[str, str]:
    """Load the most recent signal type for each symbol from before today."""
    today = date.today()
    result = {}
    for sym in symbols:
        prev = (
            db.query(Signal)
            .filter(
                Signal.symbol == sym,
                Signal.generated_at < datetime(today.year, today.month, today.day),
            )
            .order_by(Signal.generated_at.desc())
            .first()
        )
        if prev:
            result[sym] = prev.signal_type.value
    return result


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
