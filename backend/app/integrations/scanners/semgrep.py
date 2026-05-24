import subprocess
import json
from app.integrations.base import BaseIntegration


class SemgrepScanner(BaseIntegration):
    async def test_connection(self) -> bool:
        try:
            result = subprocess.run(["semgrep", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    async def sync(self) -> dict:
        return {}

    async def scan_directory(self, path: str) -> list[dict]:
        try:
            result = subprocess.run(
                ["semgrep", "--json", "--config", "auto", path],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode not in [0, 1]:
                return []
            data = json.loads(result.stdout)
            return [
                {
                    "rule_id": r.get("check_id"),
                    "message": r.get("extra", {}).get("message", ""),
                    "severity": r.get("extra", {}).get("severity", "WARNING").lower(),
                    "file": r.get("path"),
                    "line": r.get("start", {}).get("line"),
                }
                for r in data.get("results", [])
            ]
        except Exception:
            return []
