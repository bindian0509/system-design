import pandas as pd
from ta.momentum import ROCIndicator


def compute_momentum_score(
    price_df: pd.DataFrame, benchmark_df: pd.DataFrame | None = None
) -> tuple[float, dict]:
    if price_df.empty or len(price_df) < 252:
        return 0.0, {
            "relative_strength_6m": None,
            "near_52w_high": False,
            "near_52w_low": False,
            "roc_1m": None,
            "roc_3m": None,
        }

    df = price_df.sort_values("trade_date").reset_index(drop=True)
    close = df["close"]
    high = df["high"]
    low = df["low"]

    last_close = float(close.iloc[-1])
    high_52w = float(high.iloc[-252:].max())
    low_52w = float(low.iloc[-252:].min())
    range_52w = high_52w - low_52w

    near_52w_high = range_52w > 0 and (high_52w - last_close) / high_52w <= 0.05
    near_52w_low = range_52w > 0 and (last_close - low_52w) / range_52w <= 0.15

    roc_1m = None
    roc_3m = None
    if len(close) >= 21:
        roc_1m_series = ROCIndicator(close=close, window=21, fillna=True).roc()
        roc_1m = float(roc_1m_series.iloc[-1]) if not pd.isna(roc_1m_series.iloc[-1]) else None
    if len(close) >= 63:
        roc_3m_series = ROCIndicator(close=close, window=63, fillna=True).roc()
        roc_3m = float(roc_3m_series.iloc[-1]) if not pd.isna(roc_3m_series.iloc[-1]) else None

    relative_strength_6m = None
    if benchmark_df is not None and not benchmark_df.empty and len(benchmark_df) >= 126:
        bench = benchmark_df.sort_values("trade_date").reset_index(drop=True)
        if "close" in bench.columns:
            stock_ret_6m = (close.iloc[-1] / close.iloc[-126] - 1) * 100
            bench_ret_6m = (
                bench["close"].iloc[-1] / bench["close"].iloc[-126] - 1
            ) * 100
            relative_strength_6m = stock_ret_6m - bench_ret_6m

    uptrend = False
    if len(df) >= 63:
        first_half = df.iloc[-63:-31]
        second_half = df.iloc[-31:]
        if not first_half.empty and not second_half.empty:
            uptrend = (
                second_half["high"].max() > first_half["high"].max()
                and second_half["low"].min() > first_half["low"].min()
            )

    score = 0.0

    if relative_strength_6m is not None:
        if relative_strength_6m > 10:
            score += 30
        elif relative_strength_6m > 0:
            score += 25

    if near_52w_low and roc_1m is not None and roc_1m > 0:
        score += 25
    elif near_52w_high:
        score += 15

    if roc_1m is not None and roc_1m > 0:
        score += 10
    if roc_3m is not None and roc_3m > 0:
        score += 10

    if uptrend:
        score += 10

    score = min(100.0, score)

    return score, {
        "relative_strength_6m": relative_strength_6m,
        "near_52w_high": near_52w_high,
        "near_52w_low": near_52w_low,
        "roc_1m": roc_1m,
        "roc_3m": roc_3m,
    }
