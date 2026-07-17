"""Seed pipeline: for each ticker in the watchlist, fetch prices, detect
volatility points, and upsert everything into Supabase.

Writes go over a DIRECT Postgres connection (psycopg2), not the REST API —
this sidesteps corporate-proxy (Zscaler) TLS interception that breaks httpx.

Usage:
    python seed.py                # all tickers, 5y
    python seed.py NVDA AAPL      # specific tickers
"""

import sys

from psycopg2.extras import execute_values

from db import pg_connect
from detector import detect_anomalies
from fetch_prices import fetch_ohlcv
from watchlist import WATCHLIST

PERIOD = "5y"


def seed(tickers: list[str] | None = None) -> None:
    universe = [s for s in WATCHLIST if not tickers or s["ticker"] in tickers]
    conn = pg_connect()
    try:
        with conn:  # single transaction, commits on success
            with conn.cursor() as cur:
                # 1) stocks
                execute_values(
                    cur,
                    "INSERT INTO stocks (ticker, company_name, sector) VALUES %s "
                    "ON CONFLICT (ticker) DO UPDATE SET "
                    "company_name = EXCLUDED.company_name, sector = EXCLUDED.sector",
                    [(s["ticker"], s["company_name"], s["sector"]) for s in universe],
                )
                print(f"stocks: upserted {len(universe)}")

                for s in universe:
                    tk = s["ticker"]
                    df = fetch_ohlcv(tk, period=PERIOD)
                    if df.empty:
                        print(f"  {tk}: no data, skipping")
                        continue

                    bars = [(
                        tk, d.strftime("%Y-%m-%d"),
                        round(float(r.open), 4), round(float(r.high), 4),
                        round(float(r.low), 4), round(float(r.close), 4),
                        int(r.volume) if r.volume == r.volume else 0,
                    ) for d, r in df.iterrows()]
                    execute_values(
                        cur,
                        "INSERT INTO price_bars "
                        "(ticker, date, open, high, low, close, volume) VALUES %s "
                        "ON CONFLICT (ticker, date) DO UPDATE SET "
                        "open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, "
                        "close=EXCLUDED.close, volume=EXCLUDED.volume",
                        bars, page_size=1000,
                    )

                    points = detect_anomalies(df)
                    if points:
                        rows = [(
                            tk, p["date"], p["return_pct"], p["zscore"],
                            p["type"], p["volume_spike"], p["priority"],
                        ) for p in points]
                        execute_values(
                            cur,
                            "INSERT INTO anomaly_points "
                            "(ticker, date, return_pct, zscore, type, volume_spike, priority) "
                            "VALUES %s ON CONFLICT (ticker, date) DO UPDATE SET "
                            "return_pct=EXCLUDED.return_pct, zscore=EXCLUDED.zscore, "
                            "type=EXCLUDED.type, volume_spike=EXCLUDED.volume_spike, "
                            "priority=EXCLUDED.priority",
                            rows,
                        )

                    cur.execute(
                        "INSERT INTO watch_state (ticker) VALUES (%s) "
                        "ON CONFLICT (ticker) DO NOTHING",
                        (tk,),
                    )
                    print(f"  {tk}: {len(bars)} bars, {len(points)} anomaly points")
    finally:
        conn.close()
    print("✅ seed complete")


if __name__ == "__main__":
    seed(sys.argv[1:] or None)
