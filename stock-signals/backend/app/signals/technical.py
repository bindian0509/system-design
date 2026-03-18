import pandas as pd
import ta
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator
from ta.volatility import BollingerBands


def compute_technical_score(price_df: pd.DataFrame) -> tuple[float, dict]:
    if price_df.empty or len(price_df) < 200:
        return 0.0, {
            "rsi": None,
            "macd_signal": None,
            "ma_crossover": None,
            "volume_spike": False,
            "bollinger_state": None,
        }

    df = price_df.sort_values("trade_date").reset_index(drop=True)
    close = df["close"]
    volume = df["volume"]

    rsi_series = RSIIndicator(close=close, window=14, fillna=True).rsi()
    rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else None

    macd_ind = MACD(close=close, window_slow=26, window_fast=12, window_sign=9, fillna=True)
    macd_diff = macd_ind.macd_diff()

    macd_signal = "neutral"
    if len(macd_diff) >= 2:
        prev_diff = macd_diff.iloc[-2]
        curr_diff = macd_diff.iloc[-1]
        if prev_diff <= 0 and curr_diff > 0:
            macd_signal = "bullish"
        elif prev_diff >= 0 and curr_diff < 0:
            macd_signal = "bearish"

    sma_50 = SMAIndicator(close=close, window=50, fillna=True).sma_indicator()
    sma_200 = SMAIndicator(close=close, window=200, fillna=True).sma_indicator()
    price = float(close.iloc[-1])
    ma_50 = float(sma_50.iloc[-1]) if not pd.isna(sma_50.iloc[-1]) else None
    ma_200 = float(sma_200.iloc[-1]) if not pd.isna(sma_200.iloc[-1]) else None

    ma_crossover = "below_both"
    if ma_50 is not None and ma_200 is not None:
        if price > ma_200 and price > ma_50:
            ma_crossover = "above_both"
        elif price > ma_50:
            ma_crossover = "above_50_only"
        if ma_50 > ma_200:
            ma_crossover = ma_crossover + "_golden"
        elif ma_50 < ma_200:
            ma_crossover = ma_crossover + "_death"

    bb = BollingerBands(close=close, window=20, window_dev=2, fillna=True)
    bb_width = bb.bollinger_wband()
    bb_width_avg = bb_width.rolling(20, min_periods=1).mean()
    bollinger_squeeze = (
        float(bb_width.iloc[-1]) < float(bb_width_avg.iloc[-1])
        if len(bb_width) > 0 and len(bb_width_avg) > 0
        else False
    )
    bollinger_state = "squeeze" if bollinger_squeeze else "normal"

    vol_20_avg = volume.rolling(20, min_periods=1).mean().iloc[-1]
    vol_spike = float(volume.iloc[-1]) > 2.0 * float(vol_20_avg) if vol_20_avg > 0 else False
    price_up = float(close.iloc[-1]) > float(close.iloc[-2]) if len(close) >= 2 else False

    score = 0.0

    if rsi is not None:
        if rsi < 30:
            score += 25
        elif rsi < 50:
            score += 15
        elif rsi < 70:
            score += 5

    if macd_signal == "bullish":
        score += 25
    elif macd_signal == "neutral":
        score += 10

    if ma_crossover.startswith("above_both"):
        score += 15
    elif ma_crossover.startswith("above_50_only"):
        score += 10

    if "golden" in ma_crossover:
        score += 10

    if bollinger_squeeze:
        score += 10

    if vol_spike and price_up:
        score += 15

    score = round(min(100.0, score), 2)

    return score, {
        "rsi": round(rsi, 2) if rsi is not None else None,
        "macd_signal": macd_signal,
        "ma_crossover": ma_crossover,
        "volume_spike": vol_spike,
        "bollinger_state": bollinger_state,
    }
