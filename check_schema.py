
import sqlite3
import os

db_path = "backend/uniops_dev.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables:")
    for t in tables:
        print(t[0])
        cursor.execute(f"PRAGMA table_info({t[0]})")
        columns = cursor.fetchall()
        for c in columns:
            print(f"  - {c[1]} ({c[2]})")

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
