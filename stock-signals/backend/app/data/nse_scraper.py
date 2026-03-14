"""Optional NSE India scraper for delivery volume data.

NSE frequently changes its website and API structure, so this module
is designed to fail gracefully. The core platform works without it.
"""

import logging
from datetime import date

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

NSE_BASE = "https://www.nseindia.com"
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


def _get_session_cookies() -> dict:
    """NSE requires a valid session cookie from the homepage."""
    try:
        resp = httpx.get(NSE_BASE, headers=NSE_HEADERS, follow_redirects=True, timeout=10)
        return dict(resp.cookies)
    except Exception as e:
        logger.warning("Failed to get NSE session: %s", e)
        return {}


def fetch_delivery_data(symbol: str, trade_date: date | None = None) -> dict | None:
    """Fetch delivery volume data from NSE for a given symbol.

    Returns dict with delivery_quantity and delivery_pct, or None on failure.
    """
    cookies = _get_session_cookies()
    if not cookies:
        return None

    try:
        url = f"{NSE_BASE}/api/quote-equity?symbol={symbol}"
        resp = httpx.get(url, headers=NSE_HEADERS, cookies=cookies, timeout=10)
        if resp.status_code != 200:
            logger.warning("NSE API returned %d for %s", resp.status_code, symbol)
            return None

        data = resp.json()
        sec_info = data.get("securityWiseDP", {})
        return {
            "delivery_quantity": sec_info.get("deliveryQuantity"),
            "delivery_pct": sec_info.get("deliveryToTradedQuantity"),
            "total_traded_volume": sec_info.get("totalTradedVolume"),
        }
    except Exception as e:
        logger.warning("NSE delivery fetch failed for %s: %s", symbol, e)
        return None
