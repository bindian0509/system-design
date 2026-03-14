def compute_valuation_score(fundamentals: dict) -> tuple[float, dict]:
    pe = fundamentals.get("pe_ratio")
    pb = fundamentals.get("pb_ratio")
    peg = fundamentals.get("peg_ratio")
    earnings_yield = fundamentals.get("earnings_yield")
    dividend_yield = fundamentals.get("dividend_yield")
    pe_5yr_median = fundamentals.get("pe_5yr_median")

    sector_pb = 3.0
    pe_vs_median = None
    peg_assessment = None
    earnings_yield_premium = None

    score = 0.0

    if pe is not None and pe > 0 and pe_5yr_median is not None and pe_5yr_median > 0:
        ratio = pe / pe_5yr_median
        pe_vs_median = ratio
        if ratio < 0.8:
            score += 30
        elif ratio <= 1.0:
            score += 20
        elif ratio > 1.2:
            score += 5

    if peg is not None:
        if peg < 1:
            peg_assessment = "undervalued"
            score += 25
        elif peg <= 1.5:
            peg_assessment = "fair"
            score += 15
        elif peg > 2:
            peg_assessment = "overvalued"

    if earnings_yield is not None:
        ey_pct = earnings_yield * 100 if earnings_yield <= 1 else earnings_yield
        earnings_yield_premium = ey_pct
        if ey_pct > 7:
            score += 20
        elif ey_pct > 5:
            score += 10

    if dividend_yield is not None and dividend_yield >= 0:
        dy_pct = dividend_yield * 100 if dividend_yield <= 1 else dividend_yield
        if dy_pct > 1.5:
            score += 10
        elif dy_pct > 0:
            score += 5

    if pb is not None and pb < sector_pb:
        score += 15

    score = min(100.0, score)

    return score, {
        "pe_vs_median": pe_vs_median,
        "peg_assessment": peg_assessment,
        "earnings_yield_premium": earnings_yield_premium,
    }
