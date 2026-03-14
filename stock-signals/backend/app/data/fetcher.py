import logging
from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from app.models import Stock, PriceHistory
from app.data.session import get_yf_session

logger = logging.getLogger(__name__)

NSE_SUFFIX = ".NS"


def _to_yf_symbol(symbol: str) -> str:
    if not symbol.endswith(NSE_SUFFIX):
        return symbol + NSE_SUFFIX
    return symbol


def _to_clean_symbol(yf_symbol: str) -> str:
    return yf_symbol.replace(NSE_SUFFIX, "")


def fetch_stock_list_nifty500() -> list[dict]:
    """Fetch Nifty 500 constituent list. Falls back to a curated seed list
    if the live fetch fails (NSE changes URLs frequently)."""
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        df = pd.read_csv(url)
        results = []
        for _, row in df.iterrows():
            results.append(
                {
                    "symbol": row.get("Symbol", "").strip(),
                    "name": row.get("Company Name", "").strip(),
                    "industry": row.get("Industry", "").strip(),
                    "sector": row.get("Industry", "").strip(),
                }
            )
        return results
    except Exception as e:
        logger.warning("Failed to fetch Nifty 500 list: %s. Using seed list.", e)
        return _seed_stock_list()


def _seed_stock_list() -> list[dict]:
    """A curated seed of mid/small caps for bootstrapping."""
    seeds = [
        ("INOXWIND", "Inox Wind Ltd", "Renewable Energy"),
        ("KIRLOSBROS", "Kirloskar Brothers", "Industrial Manufacturing"),
        ("MGL", "Mahanagar Gas", "Gas Distribution"),
        ("CHALET", "Chalet Hotels", "Hospitality"),
        ("KPIL", "Kalpataru Projects", "Infrastructure"),
        ("UJJIVANSFB", "Ujjivan Small Finance Bank", "Banking"),
        ("SANSERA", "Sansera Engineering", "Auto Components"),
        ("SHAILY", "Shaily Engineering Plastics", "Plastics"),
        ("MAXHEALTH", "Max Healthcare", "Healthcare"),
        ("APLAPOLLO", "APL Apollo Tubes", "Steel"),
        ("CAMS", "CAMS", "Financial Services"),
        ("POLYCAB", "Polycab India", "Cables"),
        ("DEEPAKFERT", "Deepak Fertilisers", "Chemicals"),
        ("GLOBUSSPR", "Globus Spirits", "Spirits"),
        ("TATAELXSI", "Tata Elxsi", "IT Services"),
        ("ASTRAL", "Astral Ltd", "Building Materials"),
        ("KAYNES", "Kaynes Technology", "Electronics"),
        ("SONACOMS", "Sona BLW Precision", "Auto Components"),
        ("CLEAN", "Clean Science", "Specialty Chemicals"),
        ("LXCHEM", "Laxmi Organic Industries", "Chemicals"),
        ("IIFL", "IIFL Finance", "NBFC"),
        ("PERSISTENT", "Persistent Systems", "IT Services"),
        ("COFORGE", "Coforge Ltd", "IT Services"),
        ("ROUTE", "Route Mobile", "Cloud Communications"),
        ("HAPPSTMNDS", "Happiest Minds", "IT Services"),
        ("LTTS", "L&T Technology Services", "IT Services"),
        ("BRIGADE", "Brigade Enterprises", "Real Estate"),
        ("RADICO", "Radico Khaitan", "Spirits"),
        ("GRINDWELL", "Grindwell Norton", "Abrasives"),
        ("FINEORG", "Fine Organic Industries", "Chemicals"),
    ]
    return [
        {"symbol": s, "name": n, "industry": ind, "sector": ind} for s, n, ind in seeds
    ]


def sync_stock_list(db: Session) -> int:
    """Fetch and upsert stock master list into the database."""
    stocks = fetch_stock_list_nifty500()
    count = 0
    for s in stocks:
        existing = db.query(Stock).filter(Stock.symbol == s["symbol"]).first()
        if existing:
            existing.name = s["name"]
            existing.sector = s["sector"]
            existing.industry = s["industry"]
            existing.last_updated = datetime.utcnow()
        else:
            db.add(
                Stock(
                    symbol=s["symbol"],
                    name=s["name"],
                    sector=s["sector"],
                    industry=s["industry"],
                )
            )
            count += 1
    db.commit()
    logger.info("Synced %d new stocks, %d total processed", count, len(stocks))
    return len(stocks)


def fetch_price_history(
    symbol: str, period: str = "2y", db: Session | None = None
) -> pd.DataFrame:
    """Download EOD price data from Yahoo Finance and optionally persist."""
    yf_sym = _to_yf_symbol(symbol)
    try:
        session = get_yf_session()
        ticker = yf.Ticker(yf_sym, session=session)
        hist = ticker.history(period=period, auto_adjust=True)
        if hist.empty:
            logger.warning("No price data for %s", symbol)
            return pd.DataFrame()

        hist = hist.reset_index()
        hist.columns = [c.lower().replace(" ", "_") for c in hist.columns]

        rename_map = {"date": "trade_date"}
        hist.rename(columns=rename_map, inplace=True)
        if "trade_date" in hist.columns:
            hist["trade_date"] = pd.to_datetime(hist["trade_date"]).dt.date

        cols = ["trade_date", "open", "high", "low", "close", "volume"]
        available = [c for c in cols if c in hist.columns]
        hist = hist[available]

        if db is not None:
            _persist_prices(db, symbol, hist)

        return hist

    except Exception as e:
        logger.exception("Failed to fetch prices for %s: %s", symbol, e)
        return pd.DataFrame()


def _persist_prices(db: Session, symbol: str, df: pd.DataFrame) -> None:
    existing_dates = set(
        r[0]
        for r in db.query(PriceHistory.trade_date)
        .filter(PriceHistory.symbol == symbol)
        .all()
    )
    new_rows = []
    for _, row in df.iterrows():
        td = row["trade_date"]
        if isinstance(td, datetime):
            td = td.date()
        if td in existing_dates:
            continue
        new_rows.append(
            PriceHistory(
                symbol=symbol,
                trade_date=td,
                open=row.get("open"),
                high=row.get("high"),
                low=row.get("low"),
                close=row.get("close"),
                volume=row.get("volume"),
            )
        )
    if new_rows:
        db.bulk_save_objects(new_rows)
        db.commit()
        logger.info("Persisted %d new price rows for %s", len(new_rows), symbol)


def fetch_benchmark(period: str = "2y") -> pd.DataFrame:
    """Fetch Nifty 50 index data as benchmark (^NSEI on Yahoo Finance)."""
    return fetch_price_history("^NSEI", period=period)


def load_price_history_from_db(db: Session, symbol: str) -> pd.DataFrame:
    rows = (
        db.query(PriceHistory)
        .filter(PriceHistory.symbol == symbol)
        .order_by(PriceHistory.trade_date)
        .all()
    )
    if not rows:
        return pd.DataFrame()
    data = [
        {
            "trade_date": r.trade_date,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume,
        }
        for r in rows
    ]
    return pd.DataFrame(data)
