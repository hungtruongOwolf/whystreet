"""Shared DB helpers: Supabase REST client (for row I/O) and a direct
Postgres connection (for DDL / bulk work). Reads config from the repo .env."""

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

# .env lives at the repo root (whystreet/.env), one level up from detector/
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def project_ref() -> str:
    """Extract the Supabase project ref from SUPABASE_URL."""
    host = urlparse(os.environ["SUPABASE_URL"]).hostname or ""
    return host.split(".")[0]


def pg_connect():
    """Direct Postgres connection. If SUPABASE_DB_URL is set, use it directly
    (the exact string from Supabase's "Connect" dialog). Otherwise try the
    direct host, then regional session poolers (IPv4). Returns a connection."""
    import psycopg2

    db_url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if db_url:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        print("  connected via SUPABASE_DB_URL")
        return conn

    ref = project_ref()
    pwd = os.environ["SUPABASE_DB_PASSWORD"]

    attempts = [
        # Direct connection (IPv6 on newer projects, may fail on IPv4-only nets)
        dict(host=f"db.{ref}.supabase.co", port=5432, user="postgres"),
    ]
    # Session poolers across common regions (IPv4). We don't know the exact
    # region, so try the usual US ones.
    for region in ("us-west-1", "us-east-1", "us-east-2", "us-west-2"):
        attempts.append(
            dict(host=f"aws-0-{region}.pooler.supabase.com", port=5432,
                 user=f"postgres.{ref}")
        )

    last_err = None
    for kw in attempts:
        try:
            conn = psycopg2.connect(
                dbname="postgres", password=pwd, sslmode="require",
                connect_timeout=8, **kw,
            )
            print(f"  connected via {kw['host']}")
            return conn
        except Exception as e:  # noqa: BLE001 - we want to try the next host
            last_err = e
            print(f"  failed {kw['host']}: {str(e).splitlines()[0]}")
    raise RuntimeError(f"Could not connect to Postgres. Last error: {last_err}")


def supabase_client(service: bool = True):
    """Supabase REST client. service=True uses the service_role key (bypasses
    RLS, for the seed script); service=False uses the anon key."""
    from supabase import create_client

    key = os.environ["SUPABASE_SERVICE_KEY" if service else "SUPABASE_ANON_KEY"]
    return create_client(os.environ["SUPABASE_URL"], key)
