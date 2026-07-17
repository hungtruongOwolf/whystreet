"""Re-run jump detection from prices already in Supabase (no Yahoo refetch).
Replaces anomaly_points for each ticker. Use after changing detector.py.

Usage: python redetect.py           # all tickers
       python redetect.py NVDA AAPL  # specific
"""

import sys

import pandas as pd
from psycopg2.extras import execute_values

from db import pg_connect
from detector import detect_anomalies
from watchlist import WATCHLIST

COLS = ["open", "high", "low", "close", "volume"]


def main(tickers: list[str] | None = None) -> None:
    universe = [s["ticker"] for s in WATCHLIST if not tickers or s["ticker"] in tickers]
    conn = pg_connect()
    try:
        with conn:
            with conn.cursor() as cur:
                for tk in universe:
                    cur.execute(
                        "select date, open, high, low, close, volume "
                        "from price_bars where ticker=%s order by date", (tk,)
                    )
                    rows = cur.fetchall()
                    if not rows:
                        print(f"  {tk}: no price data")
                        continue
                    df = pd.DataFrame(rows, columns=["date"] + COLS)
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date")
                    for c in COLS:
                        df[c] = df[c].astype(float)

                    points = detect_anomalies(df)
                    cur.execute("delete from anomaly_points where ticker=%s", (tk,))
                    if points:
                        execute_values(
                            cur,
                            "insert into anomaly_points "
                            "(ticker, date, return_pct, zscore, type, volume_spike, priority) "
                            "values %s",
                            [(tk, p["date"], p["return_pct"], p["zscore"],
                              p["type"], p["volume_spike"], p["priority"]) for p in points],
                        )
                    print(f"  {tk}: {len(points)} jumps")
    finally:
        conn.close()
    print("✅ redetect complete")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
