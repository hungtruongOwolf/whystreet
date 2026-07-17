"""Create the WhyStreet tables by running supabase/schema.sql over a direct
Postgres connection. Idempotent (schema uses CREATE TABLE IF NOT EXISTS)."""

from pathlib import Path

from db import pg_connect

SCHEMA = Path(__file__).resolve().parent.parent / "supabase" / "schema.sql"


def main() -> None:
    sql = SCHEMA.read_text()
    print("Connecting to Postgres...")
    conn = pg_connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql)
        print("✅ Schema applied. Tables created.")
        # Verify
        with conn.cursor() as cur:
            cur.execute(
                "select table_name from information_schema.tables "
                "where table_schema='public' order by table_name"
            )
            tables = [r[0] for r in cur.fetchall()]
        print("Public tables:", ", ".join(tables))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
