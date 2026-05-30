import subprocess
import json
from app.integrations.base import BaseIntegration


class TrivyScanner(BaseIntegration):
    async def test_connection(self) -> bool:
        try:
            # Try local binary first
            result = subprocess.run(["trivy", "--version"], capture_output=True, timeout=5)
            if result.returncode == 0: return True
            # Fallback to docker
            result = subprocess.run(["docker", "run", "--rm", "aquasec/trivy:latest", "--version"], capture_output=True, timeout=15)
            return result.returncode == 0
        except Exception:
            return False

    async def sync(self) -> dict:
        return {}

    async def scan_image(self, image: str) -> list[dict]:
        try:
            # Determine best command
            cmd = ["trivy", "image", "--format", "json", "--quiet", image]
            test = subprocess.run(["trivy", "--version"], capture_output=True, timeout=5)
            if test.returncode != 0:
                cmd = ["docker", "run", "--rm", "-v", "/var/run/docker.sock:/var/run/docker.sock", "aquasec/trivy:latest", "image", "--format", "json", "--quiet", image]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=180,
            )
            if result.returncode != 0:
                return []
            data = json.loads(result.stdout)
            vulnerabilities = []
            for r in data.get("Results", []):
                for v in r.get("Vulnerabilities", []):
                    vulnerabilities.append({
                        "cve_id": v.get("VulnerabilityID"),
                        "title": v.get("Title", ""),
                        "severity": v.get("Severity", "UNKNOWN").lower(),
                        "cvss_score": v.get("CVSS", {}).get("nvd", {}).get("V3Score"),
                        "package_name": v.get("PkgName"),
                        "package_version": v.get("InstalledVersion"),
                        "fixed_version": v.get("FixedVersion",
                        "target": r.get("Target"),
                    })
            return vulnerabilities
        except Exception:
            return []
