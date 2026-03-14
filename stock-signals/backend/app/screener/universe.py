from sqlalchemy.orm import Session

from app.models import Stock, WatchlistItem


def update_universe(db_session: Session, passing_symbols: list[str]) -> None:
    db_session.query(Stock).update({Stock.is_in_universe: False})
    if passing_symbols:
        db_session.query(Stock).filter(Stock.symbol.in_(passing_symbols)).update(
            {Stock.is_in_universe: True}, synchronize_session=False
        )
    db_session.commit()


def get_universe(db_session: Session) -> list[str]:
    rows = db_session.query(Stock.symbol).filter(Stock.is_in_universe == True).all()
    return [r.symbol for r in rows]


def add_to_watchlist(db_session: Session, symbol: str, notes: str = None) -> None:
    existing = db_session.query(WatchlistItem).filter(WatchlistItem.symbol == symbol).first()
    if existing:
        existing.notes = notes
    else:
        db_session.add(WatchlistItem(symbol=symbol, notes=notes))
    db_session.commit()


def get_watchlist(db_session: Session) -> list[dict]:
    rows = db_session.query(WatchlistItem).order_by(WatchlistItem.added_at).all()
    return [{"symbol": r.symbol, "notes": r.notes, "added_at": r.added_at} for r in rows]
