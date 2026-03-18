from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Fundamentals


def _fundamental_quality_score(row) -> float:
    s = settings.screener
    score = 0.0
    if row.roe is not None and row.roe >= s.min_roe:
        score += min(25, (row.roe - s.min_roe) / 2)
    if row.roce is not None and row.roce >= s.min_roce:
        score += min(25, (row.roce - s.min_roce) / 2)
    if row.revenue_growth_3yr is not None and row.revenue_growth_3yr >= s.min_revenue_growth_3yr:
        score += min(25, (row.revenue_growth_3yr - s.min_revenue_growth_3yr) / 2)
    if row.profit_growth_3yr is not None and row.profit_growth_3yr >= s.min_profit_growth_3yr:
        score += min(25, (row.profit_growth_3yr - s.min_profit_growth_3yr) / 2)
    return round(min(100.0, score + 25), 2)


def screen_stocks(db_session: Session) -> list[str]:
    s = settings.screener
    subq = (
        db_session.query(
            Fundamentals.symbol,
            func.max(Fundamentals.as_of_date).label("max_date"),
        )
        .group_by(Fundamentals.symbol)
        .subquery()
    )

    # NULL-tolerant filters: treat NULL as passing so stocks with missing
    # data aren't silently excluded. The composite scorer still penalises
    # them through lower sub-scores.
    q = (
        db_session.query(Fundamentals)
        .join(
            subq,
            (Fundamentals.symbol == subq.c.symbol)
            & (Fundamentals.as_of_date == subq.c.max_date),
        )
        .filter(
            Fundamentals.market_cap_cr >= s.min_market_cap_cr,
            Fundamentals.market_cap_cr <= s.max_market_cap_cr,
            or_(Fundamentals.roe >= s.min_roe, Fundamentals.roe.is_(None)),
            or_(Fundamentals.roce >= s.min_roce, Fundamentals.roce.is_(None)),
            or_(
                Fundamentals.debt_equity <= s.max_debt_equity,
                Fundamentals.debt_equity.is_(None),
            ),
            or_(
                Fundamentals.promoter_holding >= s.min_promoter_holding,
                Fundamentals.promoter_holding.is_(None),
            ),
            or_(
                Fundamentals.promoter_pledge <= s.max_promoter_pledge,
                Fundamentals.promoter_pledge.is_(None),
            ),
            or_(
                Fundamentals.revenue_growth_3yr >= s.min_revenue_growth_3yr,
                Fundamentals.revenue_growth_3yr.is_(None),
            ),
            or_(
                Fundamentals.profit_growth_3yr >= s.min_profit_growth_3yr,
                Fundamentals.profit_growth_3yr.is_(None),
            ),
        )
    )
    rows = q.all()
    passing = []
    for row in rows:
        _ = _fundamental_quality_score(row)
        passing.append(row.symbol)
    return passing
