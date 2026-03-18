from app.config import settings
from app.models import SignalType


def compute_composite_signal(
    fundamental_score: float,
    technical_score: float,
    momentum_score: float,
    valuation_score: float,
    fundamental_pass: bool,
) -> tuple[float, SignalType, str, dict]:
    w = settings.weights
    composite = (
        w.fundamental * fundamental_score
        + w.technical * technical_score
        + w.momentum * momentum_score
        + w.valuation * valuation_score
    )
    composite = round(min(100.0, composite), 2)

    sub_scores = {
        "fundamental_score": round(fundamental_score, 2),
        "technical_score": round(technical_score, 2),
        "momentum_score": round(momentum_score, 2),
        "valuation_score": round(valuation_score, 2),
    }

    if composite > 80 and fundamental_pass and technical_score > 50:
        signal_type = SignalType.STRONG_BUY
    elif composite >= 60:
        signal_type = SignalType.BUY
    elif composite >= 40:
        signal_type = SignalType.HOLD
    else:
        signal_type = SignalType.EXIT

    parts = []
    parts.append(f"Composite score: {composite:.1f} (F:{fundamental_score:.0f} T:{technical_score:.0f} M:{momentum_score:.0f} V:{valuation_score:.0f})")
    if signal_type == SignalType.STRONG_BUY:
        parts.append("STRONG_BUY: Score >80, fundamental pass, and technical >50.")
    elif signal_type == SignalType.BUY:
        parts.append("BUY: Score 60-80.")
    elif signal_type == SignalType.HOLD:
        parts.append("HOLD: Score 40-60.")
    else:
        parts.append("EXIT: Score <40.")
    if not fundamental_pass and composite > 80:
        parts.append("Downgraded from STRONG_BUY: fundamental screen not passed.")
    reasoning = " ".join(parts)

    return composite, signal_type, reasoning, sub_scores
