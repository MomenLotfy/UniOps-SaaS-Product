
import sqlite3
import os

db_path = "backend/uniops_dev.db"
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("SELECT count(*) FROM vulnerabilities")
    vuln_count = cursor.fetchone()[0]
    print(f"Vulnerabilities count: {vuln_count}")

    cursor.execute("SELECT count(*) FROM threats")
    threat_count = cursor.fetchone()[0]
    print(f"Threats count: {threat_count}")

    cursor.execute("SELECT id, title, severity, status, repo_id, cve_id FROM vulnerabilities LIMIT 5")
    vulns = cursor.fetchall()
    print("\nSample Vulnerabilities:")
    for v in vulns:
        print(v)

    cursor.execute("SELECT id, title, severity, status, repo_id FROM threats LIMIT 5")
    threats = cursor.fetchall()
    print("\nSample Threats:")
    for t in threats:
        print(t)

    cursor.execute("SELECT id, name, type, status FROM integrations")
    integrations = cursor.fetchall()
    print("\nIntegrations:")
    for i in integrations:
        print(i)

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
