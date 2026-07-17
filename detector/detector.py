"""Significant-move detector — Bollinger Band breakout episodes.

Pure math, deterministic, no AI. Marks WHERE price broke out of its normal
range (the "buy range / sell range" traders watch), then the pipeline explains
WHY. See docs/03-detector.md for the decision record.

Model: a 20-day SMA (the MA line / middle band) with bands at SMA ± k·σ.
~88-89% of price sits inside the bands, so a close outside is significant.
We group consecutive out-of-band days (same side) into one breakout EPISODE and
mark its extreme (the peak of an up-breakout / trough of a down-breakout). This
captures both one-day spikes AND slow multi-week trends (which also leave the
band), unlike a single-day jump test.
"""

import numpy as np
import pandas as pd


def detect_anomalies(
    df: pd.DataFrame,
    ma_window: int = 20,
    k: float = 2.0,
    min_move_pct: float = 3.0,
    max_points: int = 15,
) -> list[dict]:
    """Detect Bollinger breakout episodes in an OHLCV DataFrame (indexed by date).

    ma_window     SMA / band window (the MA line)
    k             band width in standard deviations (2.0 = classic Bollinger)
    min_move_pct  ignore breakout legs smaller than this (noise / squeezes)
    max_points    keep the strongest N per ticker (by leg size)
    """
    if df.empty or len(df) < ma_window + 5:
        return []

    df = df.sort_index().copy()
    dates = df.index
    c = df["close"].astype(float).to_numpy()
    vol = df["volume"].astype(float).to_numpy()
    n = len(c)

    s = pd.Series(c)
    sma = s.rolling(ma_window).mean().to_numpy()
    std = s.rolling(ma_window).std().to_numpy()
    upper = sma + k * std
    lower = sma - k * std
    vol_med = pd.Series(vol).rolling(ma_window).median().to_numpy()

    # Which side of the band each day closes on (0 = inside).
    side = np.zeros(n, dtype=int)
    for i in range(n):
        if np.isnan(upper[i]):
            continue
        if c[i] > upper[i]:
            side[i] = 1
        elif c[i] < lower[i]:
            side[i] = -1

    episodes: list[dict] = []
    i = 0
    while i < n:
        if side[i] == 0:
            i += 1
            continue
        sgn = side[i]
        start = i
        while i < n and side[i] == sgn:
            i += 1
        end = i - 1  # inclusive

        seg = c[start:end + 1]
        off = int(np.argmax(seg) if sgn > 0 else np.argmin(seg))
        ext = start + off                       # extreme (peak / trough) of the episode
        pre = c[start - 1] if start > 0 else c[start]  # last in-band close before the breakout
        move = (c[ext] - pre) / pre * 100.0     # size of the whole breakout leg
        if abs(move) < min_move_pct:
            continue

        # Anchor the marker at the START of the breakout (the day price first
        # broke the band -- usually the catalyst/event day), NOT the extreme,
        # so the marker lands where the move begins rather than lagging at the top.
        anchor = start
        dev_sigma = (c[anchor] - sma[anchor]) / std[anchor] if std[anchor] else 0.0
        vspike = bool(not np.isnan(vol_med[anchor]) and vol[anchor] > 2.0 * vol_med[anchor])

        episodes.append({
            "date": dates[anchor].strftime("%Y-%m-%d"),
            "close": round(float(c[anchor]), 4),
            "return_pct": round(float(move), 2),
            "zscore": round(float(dev_sigma), 3),   # σ-distance from the MA line
            "type": ["breakout"] + (["volume_confirmed"] if vspike else []),
            "volume_spike": vspike,
            "priority": round(abs(float(move)), 3),
        })

    episodes.sort(key=lambda x: -x["priority"])
    episodes = episodes[:max_points]
    episodes.sort(key=lambda x: x["date"])
    return episodes
