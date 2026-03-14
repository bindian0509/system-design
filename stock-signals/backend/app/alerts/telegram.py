import logging

from telegram import Bot
from telegram.error import TelegramError

from app.config import settings
from app.models import AlertLog, SignalType
from app.database import SessionLocal

logger = logging.getLogger(__name__)

SIGNAL_EMOJI = {
    "STRONG_BUY": "🚀",
    "BUY": "📈",
    "HOLD": "⏸️",
    "EXIT": "📉",
}


def _signal_type_from_str(s: str) -> SignalType | None:
    try:
        return SignalType(s)
    except ValueError:
        return None


def _log_alert(symbol: str, signal_type: SignalType, message: str, success: bool):
    db = SessionLocal()
    try:
        log = AlertLog(
            symbol=symbol,
            signal_type=signal_type,
            channel="telegram",
            message=message,
            success=success,
        )
        db.add(log)
        db.commit()
    finally:
        db.close()


async def send_telegram_alert(
    symbol: str, signal_type: str, composite_score: float, reasoning: str
) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram bot token or chat_id not configured")
        return False

    st = _signal_type_from_str(signal_type)
    if st is None:
        logger.warning("Invalid signal_type: %s", signal_type)
        return False

    emoji = SIGNAL_EMOJI.get(signal_type, "📊")
    text = (
        f"{emoji} *{symbol}* — {signal_type.replace('_', ' ')}\n"
        f"Score: {composite_score:.1f}\n\n"
        f"{reasoning}"
    )

    try:
        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode="Markdown",
        )
        _log_alert(symbol, st, text[:500], True)
        return True
    except TelegramError as e:
        logger.exception("Telegram send failed: %s", e)
        _log_alert(symbol, st, str(e)[:500], False)
        return False


async def send_weekly_summary(summary: dict) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram bot token or chat_id not configured")
        return False

    lines = ["📊 *Weekly Portfolio Summary*\n"]
    for k, v in summary.items():
        lines.append(f"• {k}: {v}")
    text = "\n".join(lines)

    try:
        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode="Markdown",
        )
        db = SessionLocal()
        try:
            log = AlertLog(
                symbol="SUMMARY",
                signal_type=SignalType.HOLD,
                channel="telegram",
                message=text[:500],
                success=True,
            )
            db.add(log)
            db.commit()
        finally:
            db.close()
        return True
    except TelegramError as e:
        logger.exception("Telegram weekly summary failed: %s", e)
        return False
