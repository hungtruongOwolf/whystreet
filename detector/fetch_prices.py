"""Fetch daily OHLCV from Yahoo Finance for a ticker. Pure data, no AI."""

import pandas as pd
import yfinance as yf


def fetch_ohlcv(ticker: str, period: str = "5y", interval: str = "1d") -> pd.DataFrame:
    """Return a DataFrame indexed by date with columns:
    open, high, low, close, volume. Empty DataFrame if nothing came back."""
    raw = yf.download(
        ticker, period=period, interval=interval,
        auto_adjust=False, progress=False, threads=False,
    )
    if raw is None or raw.empty:
        return pd.DataFrame()

    # yfinance may return MultiIndex columns (('Close','NVDA')). Flatten to level 0.
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })[["open", "high", "low", "close", "volume"]].copy()

    df.index = pd.to_datetime(df.index)
    df = df.dropna(subset=["close"]).sort_index()
    return df
