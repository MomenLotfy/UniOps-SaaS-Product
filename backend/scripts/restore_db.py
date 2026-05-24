#!/usr/bin/env python3
"""Restore PostgreSQL database from a dump file.

Usage:
    python scripts/restore_db.py --input /path/to/backup.dump
"""
import argparse
import os
import subprocess
import sys
from urllib.parse import urlparse


def restore_database(input_path: str, database_url: str, clean: bool = False) -> None:
    if not os.path.exists(input_path):
        print(f"ERROR: Backup file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    parsed = urlparse(database_url)
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password

    cmd = [
        "pg_restore",
        "-h", parsed.hostname or "localhost",
        "-p", str(parsed.port or 5432),
        "-U", parsed.username or "postgres",
        "-d", parsed.path.lstrip("/"),
        "--verbose",
        "--no-owner",
        "--no-acl",
    ]
    if clean:
        cmd.append("--clean")
    cmd.append(input_path)

    print(f"[restore] Restoring from {input_path}...")
    if clean:
        print("[restore] WARNING: --clean flag will DROP existing objects before restoring!")
        confirm = input("Type 'yes' to continue: ")
        if confirm.lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0 and "already exists" not in result.stderr:
        print(f"[restore] WARNING: {result.stderr[:500]}", file=sys.stderr)

    print("[restore] Done! Database restored successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UniOps Database Restore")
    parser.add_argument("--input", required=True, help="Backup file path")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--clean", action="store_true", help="Drop existing objects before restore")
    args = parser.parse_args()

    if not args.database_url:
        print("ERROR: DATABASE_URL required", file=sys.stderr)
        sys.exit(1)

    restore_database(args.input, args.database_url, args.clean)
