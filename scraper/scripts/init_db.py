"""One-time database setup: apply supabase/schema.sql then seed.sql directly.

The Supabase REST API cannot run DDL (CREATE TABLE, policies, etc.), so this
connects straight to Postgres. Run it once after creating your project.

Usage (from the scraper/ folder, venv active):
    set SUPABASE_DB_PASSWORD=your-db-password   # PowerShell: $env:SUPABASE_DB_PASSWORD="..."
    python scripts/init_db.py

Host/user are derived from SUPABASE_URL in .env, but can be overridden:
    python scripts/init_db.py --host aws-0-<region>.pooler.supabase.com --port 5432 --user postgres.<ref>
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from dotenv import load_dotenv
from psycopg.pq import ExecStatus

ROOT = Path(__file__).resolve().parent.parent          # scraper/
SUPABASE_DIR = ROOT.parent / "supabase"                # ../supabase
load_dotenv(ROOT / ".env")


def project_ref(supabase_url: str) -> str:
    host = urlparse(supabase_url).hostname or ""
    return host.split(".")[0]                           # <ref>.supabase.co -> <ref>


# Supabase hosts on these AWS regions; the Session Pooler hostname embeds one.
_REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1", "eu-central-2", "eu-north-1",
    "ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "ap-northeast-2",
    "ap-south-1", "sa-east-1", "ca-central-1",
]


def candidate_connections(ref: str, password: str) -> list[dict]:
    """Build connection attempts: direct first, then session-pooler per region."""
    attempts: list[dict] = [
        dict(host=f"db.{ref}.supabase.co", port=5432, user="postgres",
             password=password, dbname="postgres", sslmode="require",
             connect_timeout=10, autocommit=True),
    ]
    for prefix in ("aws-0", "aws-1"):                   # Supavisor host prefixes
        for region in _REGIONS:
            attempts.append(dict(
                host=f"{prefix}-{region}.pooler.supabase.com", port=5432,
                user=f"postgres.{ref}", password=password, dbname="postgres",
                sslmode="require", connect_timeout=8, autocommit=True,
            ))
    return attempts


def auto_connect(ref: str, password: str) -> psycopg.Connection:
    """Try direct, then each regional pooler, until one connects."""
    last_err = None
    for params in candidate_connections(ref, password):
        try:
            print(f"  trying {params['host']}:{params['port']} ...", end=" ")
            conn = psycopg.connect(**params)
            print("connected!")
            return conn
        except psycopg.OperationalError as e:
            msg = str(e).splitlines()[0][:80]
            print(f"no ({msg})")
            last_err = e
    raise SystemExit(f"\nCould not connect to any host. Last error: {last_err}")


def apply_file(conn: psycopg.Connection, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    print(f"Applying {path.name} ({len(sql):,} bytes)...")
    # Use the libpq simple-query protocol so the whole file (multiple statements,
    # dollar-quoted functions) runs in one atomic call.
    res = conn.pgconn.exec_(sql.encode("utf-8"))
    if res.status == ExecStatus.FATAL_ERROR:
        msg = res.error_message.decode("utf-8", "replace")
        raise SystemExit(f"\nERROR while applying {path.name}:\n{msg}")
    print(f"  OK ({ExecStatus(res.status).name})")


def main() -> None:
    ap = argparse.ArgumentParser(description="Apply schema + seed to Supabase Postgres.")
    ap.add_argument("--password", default=os.environ.get("SUPABASE_DB_PASSWORD", ""))
    ap.add_argument("--host", help="override DB host")
    ap.add_argument("--port", type=int, default=5432)
    ap.add_argument("--user", help="override DB user")
    ap.add_argument("--no-seed", action="store_true", help="apply schema only")
    ap.add_argument(
        "--file",
        action="append",
        default=[],
        help="apply specific SQL file(s) instead of schema.sql/seed.sql "
        "(relative to the supabase/ folder, or an absolute path). Repeatable.",
    )
    args = ap.parse_args()

    supabase_url = os.environ.get("SUPABASE_URL", "")
    if not supabase_url:
        sys.exit("SUPABASE_URL not found in .env")
    if not args.password:
        sys.exit("Provide the DB password via SUPABASE_DB_PASSWORD or --password.")

    ref = project_ref(supabase_url)

    if args.host:
        # Explicit override.
        print(f"Connecting to {args.host}:{args.port} as {args.user or 'postgres'}...")
        conn = psycopg.connect(
            host=args.host, port=args.port, dbname="postgres",
            user=args.user or "postgres", password=args.password,
            sslmode="require", connect_timeout=20, autocommit=True,
        )
    else:
        print("Auto-detecting database host (direct, then regional poolers)...")
        conn = auto_connect(ref, args.password)

    try:
        if args.file:
            # Apply the explicitly requested files (in order).
            for name in args.file:
                path = Path(name)
                if not path.is_absolute():
                    path = SUPABASE_DIR / name
                apply_file(conn, path)
        else:
            apply_file(conn, SUPABASE_DIR / "schema.sql")
            if not args.no_seed:
                apply_file(conn, SUPABASE_DIR / "seed.sql")
    finally:
        conn.close()

    print("\nDone. Schema + seed applied successfully.")


if __name__ == "__main__":
    main()
