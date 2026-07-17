"""Wipe cached analyses + the accumulated knowledge graph so everything is
re-generated fresh (with the new source-validation). Keeps base data
(stocks, price_bars, anomaly_points)."""
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")
conn = psycopg2.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=10)
with conn:
    with conn.cursor() as cur:
        for t in ("analysis_results", "kg_edges", "kg_nodes"):
            try:
                cur.execute(f"delete from {t}")
                print("cleared", t)
            except Exception as e:
                print("skip", t, "-", str(e).splitlines()[0])
conn.close()
print("✅ reset done — analyses + knowledge graph cleared")
