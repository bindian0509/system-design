import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings
from app.models import AlertLog, SignalType
from app.database import SessionLocal

logger = logging.getLogger(__name__)


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
            channel="email",
            message=message,
            success=success,
        )
        db.add(log)
        db.commit()
    finally:
        db.close()


def _html_alert(symbol: str, signal_type: str, composite_score: float, reasoning: str) -> str:
    return f"""
    <html>
    <body>
    <h2>Stock Signal: {symbol}</h2>
    <p><strong>Signal:</strong> {signal_type.replace('_', ' ')}</p>
    <p><strong>Composite Score:</strong> {composite_score:.1f}</p>
    <hr/>
    <p>{reasoning}</p>
    </body>
    </html>
    """


def send_email_alert(
    symbol: str, signal_type: str, composite_score: float, reasoning: str
) -> bool:
    if not settings.email_user or not settings.email_password or not settings.email_recipients:
        logger.warning("SMTP credentials or recipients not configured")
        return False

    st = _signal_type_from_str(signal_type)
    if st is None:
        logger.warning("Invalid signal_type: %s", signal_type)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{signal_type}] {symbol} — Score {composite_score:.1f}"
    msg["From"] = settings.email_user
    msg["To"] = settings.email_recipients
    msg.attach(MIMEText(_html_alert(symbol, signal_type, composite_score, reasoning), "html"))

    try:
        with smtplib.SMTP(settings.email_host, settings.email_port) as server:
            server.starttls()
            server.login(settings.email_user, settings.email_password)
            recipients = [r.strip() for r in settings.email_recipients.split(",")]
            server.sendmail(settings.email_user, recipients, msg.as_string())
        _log_alert(symbol, st, msg["Subject"], True)
        return True
    except smtplib.SMTPException as e:
        logger.exception("Email send failed: %s", e)
        _log_alert(symbol, st, str(e)[:500], False)
        return False


def send_weekly_email_summary(summary: dict) -> bool:
    if not settings.email_user or not settings.email_password or not settings.email_recipients:
        logger.warning("SMTP credentials or recipients not configured")
        return False

    rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in summary.items())
    html = f"""
    <html>
    <body>
    <h2>Weekly Portfolio Summary</h2>
    <table border="1" cellpadding="8">
    {rows}
    </table>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Weekly Stock Signals Summary"
    msg["From"] = settings.email_user
    msg["To"] = settings.email_recipients
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.email_host, settings.email_port) as server:
            server.starttls()
            server.login(settings.email_user, settings.email_password)
            recipients = [r.strip() for r in settings.email_recipients.split(",")]
            server.sendmail(settings.email_user, recipients, msg.as_string())
        db = SessionLocal()
        try:
            log = AlertLog(
                symbol="SUMMARY",
                signal_type=SignalType.HOLD,
                channel="email",
                message="Weekly summary",
                success=True,
            )
            db.add(log)
            db.commit()
        finally:
            db.close()
        return True
    except smtplib.SMTPException as e:
        logger.exception("Email weekly summary failed: %s", e)
        return False
