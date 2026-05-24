#!/usr/bin/env python3
"""Backup PostgreSQL database to a compressed dump file.

Usage:
    python scripts/backup_db.py [--output /path/to/backup.dump]
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse


def backup_database(output_path: str, database_url: str) -> None:
    parsed = urlparse(database_url)
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password

    cmd = [
        "pg_dump",
        "-h", parsed.hostname or "localhost",
        "-p", str(parsed.port or 5432),
        "-U", parsed.username or "postgres",
        "-d", parsed.path.lstrip("/"),
        "--format=custom",
        "--compress=9",
        "--verbose",
        "--file", output_path,
    ]

    print(f"[backup] Starting backup to {output_path}")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[backup] ERROR: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"[backup] Done! Backup size: {size_mb:.2f} MB → {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UniOps Database Backup")
    parser.add_argument("--output", default=None, help="Output file path")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"), help="Database URL")
    args = parser.parse_args()

    if not args.database_url:
        print("ERROR: DATABASE_URL env var or --database-url required", file=sys.stderr)
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = args.output or f"backups/uniops_backup_{timestamp}.dump"
    os.makedirs(os.path.dirname(output) if "/" in output else ".", exist_ok=True)

    backup_database(output, args.database_url)
