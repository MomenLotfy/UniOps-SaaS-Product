from __future__ import annotations
"""
DevSecOps Scan Engine
=====================
Orchestrates security scanners against a cloned Git repository.

Scanners (with Docker-free fallbacks):
  1. SAST          — Semgrep Docker → fallback: bandit (pip) / eslint
  2. Dependency    — OWASP DC Docker → fallback: pip-audit / npm audit (pip)
  3. Secrets       — Gitleaks Docker → fallback: regex patterns (built-in)
  4. Container     — Trivy Docker    → fallback: dockerfile lint (built-in)
  5. CI/CD         — Static YAML analysis (no Docker needed, always works)

فلو ما عنده Docker — كل scanner بيرجع results من الـ fallback
فلو الـ fallback كمان مش موجود — بيرجع list فاضية بدل ما يـcrash
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.utils.logger import logger

# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RawFinding:
    scanner:      str
    severity:     str
    title:        str
    description:  str = ""
    cve_id:       Optional[str] = None
    package:      Optional[str] = None
    version:      Optional[str] = None
    fixed_in:     Optional[str] = None
    file_path:    Optional[str] = None
    line:         Optional[int] = None
    rule_id:      Optional[str] = None
    mitre_tactic: Optional[str] = None
    raw:          dict = field(default_factory=dict)


@dataclass
class ScanResult:
    findings:       list[RawFinding] = field(default_factory=list)
    scanners_run:   dict = field(default_factory=dict)
    raw_by_scanner: dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _norm_severity(s: str) -> str:
    s = (s or "").lower()
    if s in ("critical", "blocker"):        return "critical"
    if s in ("high", "major", "error"):     return "high"
    if s in ("medium", "moderate", "warn"): return "medium"
    return "low"


async def _run(cmd: list[str], cwd: str = "/", timeout: int = 120) -> tuple[int, str, str]:
    """Run a subprocess asynchronously. Hard timeout prevents hanging."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")
    except asyncio.TimeoutError:
        logger.warning(f"Command timed out ({timeout}s): {' '.join(cmd[:3])}")
        try:
            proc.kill()
        except Exception:
            pass
        return 124, "", "timeout"
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"
    except Exception as e:
        return 1, "", str(e)


def _docker_available() -> bool:
    """Quick check — mocked for environments without Docker."""
    if not shutil.which("docker"):
        return False
    # Try docker info with very short timeout
    try:
        result = subprocess.run(
            ["docker", "info"],
            timeout=3,
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False


DOCKER_OK = None  # cached after first check


def _get_docker_available() -> bool:
    global DOCKER_OK
    if DOCKER_OK is None:
        DOCKER_OK = _docker_available()
        if not DOCKER_OK:
            logger.warning("Docker not available — using lightweight fallback scanners")
    return DOCKER_OK


# ─────────────────────────────────────────────────────────────────────────────
# Scanner 1: SAST
# ─────────────────────────────────────────────────────────────────────────────

class SastScanner:
    """
    Docker available   → Semgrep (comprehensive)
    No Docker          → bandit (Python) or built-in regex patterns
    """

    SONARQUBE_URL   = os.getenv("SONARQUBE_URL", "")
    SONARQUBE_TOKEN = os.getenv("SONARQUBE_TOKEN", "")

    async def run(self, repo_path: str, language: str) -> list[RawFinding]:
        if _get_docker_available():
            try:
                findings = await self._semgrep_docker(repo_path, language)
                if findings is not None:
                    return findings
            except Exception as e:
                logger.warning(f"Semgrep Docker failed: {e}")

        # Fallback: bandit for Python, built-in regex for others
        return await self._fallback_sast(repo_path, language)

    async def _semgrep_docker(self, repo_path: str, language: str) -> list[RawFinding]:
        rules = "p/security-audit,p/owasp-top-ten,p/secrets"
        if language == "python":           rules += ",p/python"
        if language in ("javascript","typescript"): rules += ",p/javascript"
        if language == "java":             rules += ",p/java"
        if language == "go":               rules += ",p/golang"

        cmd = [
            "docker", "run", "--rm",
            "--network", "none",           # no network needed
            "-v", f"{repo_path}:/src:ro",
            "returntocorp/semgrep:latest",
            "semgrep", "--config", rules,
            "--json", "--quiet", "--no-git-ignore", "/src",
        ]
        rc, stdout, stderr = await _run(cmd, timeout=90)
        if rc not in (0, 1):
            return []
        try:
            data = json.loads(stdout)
        except Exception:
            return []

        findings = []
        for r in data.get("results", []):
            meta = r.get("extra", {})
            findings.append(RawFinding(
                scanner=    "sast",
                severity=   _norm_severity(meta.get("severity", "warning")),
                title=      r.get("check_id", "SAST Finding"),
                description=meta.get("message", ""),
                file_path=  r.get("path", "").replace("/src/", ""),
                line=       r.get("start", {}).get("line"),
                rule_id=    r.get("check_id"),
                raw=        r,
            ))
        return findings

    async def _fallback_sast(self, repo_path: str, language: str) -> list[RawFinding]:
        """
        Lightweight SAST without Docker:
        - Python: bandit (if installed via pip)
        - All: built-in dangerous pattern regex
        """
        findings = []

        # Try bandit for Python
        if language == "python" and shutil.which("bandit"):
            rc, stdout, _ = await _run(
                ["bandit", "-r", repo_path, "-f", "json", "-q"],
                timeout=60,
            )
            if rc in (0, 1):
                try:
                    data = json.loads(stdout)
                    for issue in data.get("results", []):
                        findings.append(RawFinding(
                            scanner=    "sast",
                            severity=   _norm_severity(issue.get("issue_severity", "medium")),
                            title=      issue.get("test_name", "Security Issue"),
                            description=issue.get("issue_text", ""),
                            file_path=  issue.get("filename", "").replace(repo_path, ""),
                            line=       issue.get("line_number"),
                            rule_id=    issue.get("test_id"),
                            raw=        issue,
                        ))
                    return findings
                except Exception:
                    pass

        # Built-in dangerous patterns (works for any language, no tools needed)
        dangerous_patterns = [
            (r'eval\s*\(', "high",   "Dangerous eval() usage",        "SAST-001"),
            (r'exec\s*\(', "high",   "Dangerous exec() usage",        "SAST-002"),
            (r'os\.system\s*\(', "medium", "Shell injection risk via os.system", "SAST-003"),
            (r'subprocess\.call\s*\(.*shell\s*=\s*True', "high", "Shell injection via subprocess", "SAST-004"),
            (r'pickle\.loads?\s*\(', "high", "Unsafe pickle deserialization",   "SAST-005"),
            (r'yaml\.load\s*\([^)]*\)', "medium", "Unsafe YAML load (use safe_load)", "SAST-006"),
            (r'md5\s*\(|hashlib\.md5', "medium", "Weak MD5 hashing used",           "SAST-007"),
            (r'sha1\s*\(|hashlib\.sha1', "low", "Weak SHA1 hashing used",         "SAST-008"),
            (r'random\.(random|randint|choice)\s*\(', "low", "Non-cryptographic random", "SAST-009"),
            (r'assert\s+', "low", "Assert used (disabled in optimized mode)", "SAST-010"),
        ]

        root = Path(repo_path)
        extensions = {".py", ".js", ".ts", ".java", ".go", ".php", ".rb"}
        scanned = 0

        for fpath in root.rglob("*"):
            if not fpath.is_file() or fpath.suffix not in extensions:
                continue
            if any(part.startswith(".") or part in ("node_modules", "venv", "__pycache__", "dist")
                   for part in fpath.parts):
                continue
            if scanned >= 100:   # cap to avoid hanging
                break
            scanned += 1

            try:
                content = fpath.read_text(errors="replace")
                lines   = content.splitlines()
                rel_path = str(fpath.relative_to(root))

                for pattern, severity, title, rule_id in dangerous_patterns:
                    for i, line in enumerate(lines):
                        if re.search(pattern, line):
                            findings.append(RawFinding(
                                scanner=    "sast",
                                severity=   severity,
                                title=      title,
                                description=f"Found in {rel_path}:{i+1} — {line.strip()[:100]}",
                                file_path=  rel_path,
                                line=       i + 1,
                                rule_id=    rule_id,
                                raw=        {"pattern": pattern, "line": line.strip()[:200]},
                            ))
            except Exception:
                continue

        return findings


# ─────────────────────────────────────────────────────────────────────────────
# Scanner 2: Dependency Check
# ─────────────────────────────────────────────────────────────────────────────

class DependencyScanner:
    """
    Docker available → OWASP Dependency-Check
    No Docker        → pip-audit (Python) / npm audit (Node) — installed via pip
    """

    async def run(self, repo_path: str, language: str) -> list[RawFinding]:
        if _get_docker_available():
            findings = await self._owasp_dc(repo_path)
            if findings:
                return findings

        if language == "python":
            return await self._pip_audit(repo_path)
        if language in ("javascript", "typescript", "node"):
            return await self._npm_audit(repo_path)
        return []

    async def _owasp_dc(self, repo_path: str) -> list[RawFinding]:
        report_dir = tempfile.mkdtemp()
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{repo_path}:/src:ro",
            "-v", f"{report_dir}:/report",
            "owasp/dependency-check:latest",
            "--scan", "/src", "--format", "JSON",
            "--out", "/report", "--failOnCVSS", "0",
        ]
        await _run(cmd, timeout=120)
        report_file = Path(report_dir) / "dependency-check-report.json"
        if not report_file.exists():
            shutil.rmtree(report_dir, ignore_errors=True)
            return []
        try:
            data = json.loads(report_file.read_text())
        except Exception:
            shutil.rmtree(report_dir, ignore_errors=True)
            return []

        findings = []
        for dep in data.get("dependencies", []):
            for vuln in dep.get("vulnerabilities", []):
                findings.append(RawFinding(
                    scanner=    "deps",
                    severity=   _norm_severity(vuln.get("severity", "medium")),
                    title=      vuln.get("name", "CVE"),
                    description=vuln.get("description", ""),
                    cve_id=     vuln.get("name") if vuln.get("name", "").startswith("CVE-") else None,
                    package=    dep.get("fileName", ""),
                    version=    dep.get("version", ""),
                    raw=        vuln,
                ))
        shutil.rmtree(report_dir, ignore_errors=True)
        return findings

    async def _pip_audit(self, repo_path: str) -> list[RawFinding]:
        # Install pip-audit if not present
        if not shutil.which("pip-audit"):
            await _run(["pip", "install", "--quiet", "pip-audit"], timeout=60)

        rc, stdout, _ = await _run(
            ["pip-audit", "--format", "json", "--progress-spinner", "off"],
            cwd=repo_path, timeout=120,
        )
        try:
            data = json.loads(stdout)
        except Exception:
            return []
        findings = []
        for item in data:
            for vuln in item.get("vulns", []):
                findings.append(RawFinding(
                    scanner=    "deps",
                    severity=   "high",
                    title=      vuln.get("id", "Vulnerability"),
                    description=vuln.get("description", ""),
                    cve_id=     vuln.get("id") if "CVE" in vuln.get("id", "") else None,
                    package=    item.get("name", ""),
                    version=    item.get("version", ""),
                    fixed_in=   ",".join(vuln.get("fix_versions", [])),
                    raw=        vuln,
                ))
        return findings

    async def _npm_audit(self, repo_path: str) -> list[RawFinding]:
        pkg_json = Path(repo_path) / "package.json"
        if not pkg_json.exists():
            return []
        rc, stdout, _ = await _run(
            ["npm", "audit", "--json"],
            cwd=repo_path, timeout=120,
        )
        try:
            data = json.loads(stdout)
        except Exception:
            return []
        findings = []
        for name, vuln in data.get("vulnerabilities", {}).items():
            findings.append(RawFinding(
                scanner=    "deps",
                severity=   _norm_severity(vuln.get("severity", "medium")),
                title=      vuln.get("title", f"npm:{name}"),
                description=vuln.get("overview", ""),
                package=    name,
                version=    vuln.get("range", ""),
                raw=        vuln,
            ))
        return findings


# ─────────────────────────────────────────────────────────────────────────────
# Scanner 3: Secrets Detection
# ─────────────────────────────────────────────────────────────────────────────

class SecretsScanner:
    """
    Docker available → Gitleaks v8 (comprehensive)
    No Docker        → Built-in regex patterns for common secrets
    """

    # Built-in patterns — work without any tools
    SECRET_PATTERNS = [
        (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?([A-Za-z0-9\-_]{16,})',     "API Key",           "SEC-001"),
        (r'(?i)(secret[_-]?key|secretkey)\s*[=:]\s*["\']?([A-Za-z0-9\-_]{16,})','Secret Key',        "SEC-002"),
        (r'(?i)(access[_-]?token)\s*[=:]\s*["\']?([A-Za-z0-9\-_\.]{16,})',       "Access Token",      "SEC-003"),
        (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']([^"\']{6,})["\']',            "Hardcoded Password","SEC-004"),
        (r'AKIA[0-9A-Z]{16}',                                                      "AWS Access Key ID", "SEC-005"),
        (r'(?i)aws[_\-]?secret[_\-]?access[_\-]?key\s*[=:]\s*["\']?([A-Za-z0-9/+]{40})', "AWS Secret Key", "SEC-006"),
        (r'ghp_[A-Za-z0-9]{36}',                                                   "GitHub PAT",        "SEC-007"),
        (r'glpat-[A-Za-z0-9\-_]{20}',                                              "GitLab PAT",        "SEC-008"),
        (r'sk-[A-Za-z0-9]{32,}',                                                   "OpenAI API Key",    "SEC-009"),
        (r'(?i)-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----',                  "Private Key",       "SEC-010"),
        (r'(?i)(database[_-]?url|db[_-]?url)\s*[=:]\s*["\']?[a-z]+://[^:]+:[^@]+@', "DB URL with Creds","SEC-011"),
        (r'eyJ[A-Za-z0-9\-_=]{20,}\.eyJ[A-Za-z0-9\-_=]{20,}',                    "JWT Token",         "SEC-012"),
    ]

    # Files to skip
    SKIP_DIRS  = {".git", "node_modules", "venv", "__pycache__", "dist", "build", ".next"}
    SKIP_EXTS  = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2",
                  ".ttf", ".eot", ".mp4", ".mp3", ".zip", ".tar", ".gz", ".lock"}

    async def run(self, repo_path: str) -> list[RawFinding]:
        if _get_docker_available():
            try:
                findings = await self._gitleaks(repo_path)
                if findings is not None:
                    return findings
            except Exception as e:
                logger.warning(f"Gitleaks Docker failed: {e}")

        return await self._regex_scan(repo_path)

    async def _gitleaks(self, repo_path: str) -> list[RawFinding]:
        report_file = tempfile.mktemp(suffix=".json")
        report_dir  = os.path.dirname(report_file)
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{repo_path}:/repo:ro",
            "-v", f"{report_dir}:/report",
            "zricethezav/gitleaks:v8.18.0",
            "detect", "--source", "/repo",
            "--report-format", "json",
            "--report-path", f"/report/{os.path.basename(report_file)}",
            "--no-git", "--exit-code", "0",
        ]
        await _run(cmd, timeout=60)
        try:
            data = json.loads(Path(report_file).read_text())
        except Exception:
            return []

        return [
            RawFinding(
                scanner=     "secrets",
                severity=    "critical",
                title=       f"Secret Leaked: {leak.get('RuleID', 'unknown')}",
                description= f"Possible {leak.get('Description', 'secret')} found in "
                             f"{leak.get('File', '?')}:{leak.get('StartLine', '?')}",
                file_path=   leak.get("File"),
                line=        leak.get("StartLine"),
                rule_id=     leak.get("RuleID"),
                mitre_tactic="TA0006",
                raw=         {k: v for k, v in leak.items() if k != "Secret"},
            )
            for leak in (data if isinstance(data, list) else [])
        ]

    async def _regex_scan(self, repo_path: str) -> list[RawFinding]:
        """Regex-based secret detection — no Docker, no pip needed."""
        findings = []
        root     = Path(repo_path)
        scanned  = 0

        for fpath in root.rglob("*"):
            if not fpath.is_file():
                continue
            if any(part in self.SKIP_DIRS for part in fpath.parts):
                continue
            if fpath.suffix.lower() in self.SKIP_EXTS:
                continue
            if scanned >= 200:
                break
            scanned += 1

            try:
                content = fpath.read_text(errors="replace")
                rel     = str(fpath.relative_to(root))

                for pattern, title, rule_id in self.SECRET_PATTERNS:
                    for m in re.finditer(pattern, content, re.MULTILINE):
                        line_no = content[:m.start()].count("\n") + 1
                        findings.append(RawFinding(
                            scanner=     "secrets",
                            severity=    "critical",
                            title=       f"Potential {title}",
                            description= f"Found in {rel}:{line_no} — value redacted for security",
                            file_path=   rel,
                            line=        line_no,
                            rule_id=     rule_id,
                            mitre_tactic="TA0006",
                            raw=         {"file": rel, "line": line_no, "rule": rule_id},
                        ))
            except Exception:
                continue

        return findings


# ─────────────────────────────────────────────────────────────────────────────
# Scanner 4: Container Security
# ─────────────────────────────────────────────────────────────────────────────

class ContainerScanner:
    """
    Docker available → Trivy
    No Docker        → Built-in Dockerfile lint rules
    """

    DOCKERFILE_RULES = [
        (r"^FROM\s+\S+:latest",    "high",   "Using :latest tag makes builds non-reproducible", "CONT-001"),
        (r"(?i)^USER\s+root",      "high",   "Container running as root user",                  "CONT-002"),
        (r"(?i)^RUN\s+.*sudo",     "medium", "Using sudo in container (unnecessary)",            "CONT-003"),
        (r"(?i)ADD\s+https?://",   "medium", "ADD from URL is insecure, use COPY + curl",        "CONT-004"),
        (r"(?i)--no-check-certificate|--insecure", "high", "Disabling SSL verification",         "CONT-005"),
        (r"(?i)apt-get install.*-y(?!.*--no-install-recommends)", "low", "Missing --no-install-recommends", "CONT-006"),
        (r"(?i)EXPOSE\s+22\b",     "medium", "Exposing SSH port 22",                             "CONT-007"),
        (r"(?i)ENV\s+\w*(PASSWORD|SECRET|KEY|TOKEN)\w*\s*=", "critical", "Secret in ENV variable", "CONT-008"),
    ]

    async def run(self, repo_path: str) -> list[RawFinding]:
        dockerfile = Path(repo_path) / "Dockerfile"
        if not dockerfile.exists():
            return []

        if _get_docker_available():
            try:
                return await self._trivy(repo_path)
            except Exception as e:
                logger.warning(f"Trivy failed: {e}")

        return self._lint_dockerfile(dockerfile, repo_path)

    async def _trivy(self, repo_path: str) -> list[RawFinding]:
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{repo_path}:/repo:ro",
            "aquasec/trivy:latest",
            "config", "--format", "json", "--exit-code", "0", "/repo",
        ]
        rc, stdout, _ = await _run(cmd, timeout=120)
        try:
            data = json.loads(stdout)
        except Exception:
            return []
        findings = []
        for result in data.get("Results", []):
            for mis in result.get("Misconfigurations", []):
                findings.append(RawFinding(
                    scanner=    "container",
                    severity=   _norm_severity(mis.get("Severity", "medium")),
                    title=      mis.get("Title", "Misconfiguration"),
                    description=mis.get("Description", ""),
                    file_path=  "Dockerfile",
                    rule_id=    mis.get("ID"),
                    raw=        mis,
                ))
        return findings

    def _lint_dockerfile(self, dockerfile: Path, repo_path: str) -> list[RawFinding]:
        """Regex-based Dockerfile lint — no Docker needed."""
        findings = []
        try:
            lines = dockerfile.read_text(errors="replace").splitlines()
            has_user = any(re.match(r"(?i)^USER\s+(?!root)", l) for l in lines)
            if not has_user:
                findings.append(RawFinding(
                    scanner=    "container",
                    severity=   "high",
                    title=      "No non-root USER directive",
                    description="Container may run as root. Add USER directive.",
                    file_path=  "Dockerfile",
                    rule_id=    "CONT-000",
                ))
            for i, line in enumerate(lines):
                for pattern, severity, desc, rule_id in self.DOCKERFILE_RULES:
                    if re.search(pattern, line):
                        findings.append(RawFinding(
                            scanner=    "container",
                            severity=   severity,
                            title=      desc,
                            description=f"Dockerfile line {i+1}: {line.strip()[:100]}",
                            file_path=  "Dockerfile",
                            line=       i + 1,
                            rule_id=    rule_id,
                            raw=        {"line": line.strip()},
                        ))
        except Exception:
            pass
        return findings


# ─────────────────────────────────────────────────────────────────────────────
# Scanner 5: CI/CD (No Docker needed — pure Python)
# ─────────────────────────────────────────────────────────────────────────────

class CiCdScanner:
    """Static analysis of CI/CD YAML — always works, no Docker needed."""

    CHECKS = [
        {
            "id":      "CICD-001",
            "severity":"critical",
            "title":   "Hardcoded Secret in CI/CD",
            "pattern": r'(?i)(password|secret|token|api_key)\s*[:=]\s*["\']?[A-Za-z0-9+/]{8,}',
            "desc":    "Hardcoded credentials found. Use repository secrets instead.",
            "mitre":   "TA0006",
        },
        {
            "id":      "CICD-002",
            "severity":"high",
            "title":   "Unpinned GitHub Action (Supply Chain Risk)",
            "pattern": r'uses:\s+[\w\-]+/[\w\-]+@(?!v\d|[a-f0-9]{40})',
            "desc":    "Action not pinned to a commit SHA — supply chain attack risk.",
            "mitre":   "TA0001",
        },
        {
            "id":      "CICD-003",
            "severity":"high",
            "title":   "Overly Permissive Permissions (write-all)",
            "pattern": r'permissions\s*:\s*write-all',
            "desc":    "Workflow has write-all permissions. Use least privilege.",
            "mitre":   "TA0004",
        },
        {
            "id":      "CICD-004",
            "severity":"medium",
            "title":   "Self-Hosted Runner Risk",
            "pattern": r'runs-on\s*:\s*self-hosted',
            "desc":    "Self-hosted runners persist state between runs.",
            "mitre":   "TA0003",
        },
        {
            "id":      "CICD-005",
            "severity":"medium",
            "title":   "Script Injection via User Input",
            "pattern": r'\$\{\{\s*github\.(event\.pull_request\.|head_commit\.message)',
            "desc":    "User-controlled input used in shell script — injection risk.",
            "mitre":   "TA0002",
        },
    ]

    async def run(self, repo_path: str) -> list[RawFinding]:
        findings = []
        ci_files = self._find_ci_files(repo_path)

        for ci_file in ci_files:
            try:
                content = Path(ci_file).read_text(errors="replace")
            except Exception:
                continue

            for check in self.CHECKS:
                matches = re.findall(check["pattern"], content, re.MULTILINE)
                for m in matches[:3]:
                    findings.append(RawFinding(
                        scanner=     "cicd",
                        severity=    check["severity"],
                        title=       check["title"],
                        description= check["desc"],
                        file_path=   str(Path(ci_file).relative_to(repo_path)),
                        rule_id=     check["id"],
                        mitre_tactic=check["mitre"],
                        raw=         {"match": str(m)[:100]},
                    ))

            # Missing timeout check
            if "timeout-minutes" not in content and "jobs:" in content:
                findings.append(RawFinding(
                    scanner=    "cicd",
                    severity=   "low",
                    title=      "Missing Job Timeout",
                    description="Jobs without timeout-minutes can run indefinitely.",
                    file_path=  str(Path(ci_file).relative_to(repo_path)),
                    rule_id=    "CICD-006",
                    raw=        {},
                ))

        return findings

    def _find_ci_files(self, repo_path: str) -> list[str]:
        files = []
        root  = Path(repo_path)
        for pattern in [
            ".github/workflows/*.yml", ".github/workflows/*.yaml",
            ".gitlab-ci.yml", ".gitlab-ci.yaml",
            "Jenkinsfile", ".circleci/config.yml",
        ]:
            files.extend(str(f) for f in root.glob(pattern) if f.is_file())
        return files


# ─────────────────────────────────────────────────────────────────────────────
# Result Adapter
# ─────────────────────────────────────────────────────────────────────────────

class ResultAdapter:
    @staticmethod
    def to_threats(
        findings: list[RawFinding],
        tenant_id: str,
        scan_id: str,
        repo_full_name: str,
        repo_id: str | None = None,
    ) -> list[dict]:
        """
        Convert raw scan findings to Threat dicts.
        repo_id is stored on every record so queries can be repo-isolated.
        """
        threats = []
        for f in findings:
            if f.cve_id:
                continue
            category_map = {
                "secrets":   "credential_exposure",
                "cicd":      "cicd_misconfiguration",
                "sast":      "code_vulnerability",
                "container": "container_misconfiguration",
                "deps":      "vulnerable_dependency",
            }
            loc = f"{f.file_path}:{f.line}" if f.file_path and f.line else (f.file_path or repo_full_name)
            threats.append({
                "tenant_id":       tenant_id,
                "scan_id":         scan_id,
                # ── Repo isolation ───────────────────────────────────────────
                "repo_id":         repo_id,
                "title":           f.title[:499],
                "description":     (f.description or "")[:2000],
                "severity":        f.severity,
                "category":        category_map.get(f.scanner, f.scanner),
                "source":          f"scan:{f.scanner}",
                "status":          "open",
                "resource":        loc,
                "mitre_tactic":    f.mitre_tactic or "TA0001",
                "mitre_technique": f.rule_id,
                "raw_data": {
                    "scanner": f.scanner,
                    "file":    f.file_path,
                    "line":    f.line,
                    "rule_id": f.rule_id,
                },
            })
        return threats

    @staticmethod
    def to_vulnerabilities(
        findings: list[RawFinding],
        tenant_id: str,
        scan_id: str,
        repo_full_name: str,
        repo_id: str | None = None,
    ) -> list[dict]:
        """
        Convert raw scan findings to Vulnerability dicts.
        repo_id is stored on every record so queries can be repo-isolated.
        scanner_name is included for the deduplication engine in run_scan.py.
        """
        vulns = []
        for f in findings:
            if not f.cve_id and f.scanner not in ("deps", "container"):
                continue
            vulns.append({
                "tenant_id":       tenant_id,
                "scan_id":         scan_id,
                # ── Repo isolation ───────────────────────────────────────────
                "repo_id":         repo_id,
                "cve_id":          f.cve_id,
                "title":           f.title[:499],
                "description":     (f.description or "")[:2000],
                "severity":        f.severity,
                "status":          "open",
                "package_name":    f.package,
                "package_version": f.version,
                "fixed_version":   f.fixed_in,
                "target":          repo_full_name,
                "image":           None,
                "references":      [],
                # ── Deduplication key — consumed by _upsert_vulnerability ───
                "scanner_name":    f.scanner,
            })
        return vulns


# ─────────────────────────────────────────────────────────────────────────────
# Score Calculator
# ─────────────────────────────────────────────────────────────────────────────

class ScoreCalculator:
    @staticmethod
    def compute(findings: list[RawFinding]) -> float:
        score        = 100.0
        counts       = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        secret_count = cicd_count = 0

        for f in findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
            if f.scanner == "secrets": secret_count += 1
            if f.scanner == "cicd":    cicd_count   += 1

        score -= min(counts["critical"] * 20, 40)
        score -= min(counts["high"]     * 10, 30)
        score -= min(counts["medium"]   *  5, 15)
        score -= min(counts["low"]      *  1,  5)
        score -= min(secret_count       * 25, 50)
        score -= min(cicd_count         *  8, 16)

        return max(round(score, 1), 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# AI Analyzer
# ─────────────────────────────────────────────────────────────────────────────

class AiAnalyzer:
    async def analyze(self, repo_name: str, findings: list[RawFinding], score: float) -> tuple[str, list[str]]:
        if not findings:
            return (
                f"No security issues found in {repo_name}. Security score: {score}/100.",
                ["Schedule regular scans.", "Keep dependencies updated."],
            )
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20) as c:
                resp = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"Content-Type": "application/json"},
                    json={
                        "model":    "claude-sonnet-4-20250514",
                        "max_tokens": 800,
                        "system":   "DevSecOps engineer. Respond ONLY with JSON: {\"summary\": \"string\", \"suggestions\": [\"string\"]}. No markdown.",
                        "messages": [{"role": "user", "content": self._build_prompt(repo_name, findings, score)}],
                    },
                )
            text   = resp.json()["content"][0]["text"]
            text   = re.sub(r"```json|```", "", text).strip()
            parsed = json.loads(text)
            return parsed.get("summary", ""), parsed.get("suggestions", [])
        except Exception as e:
            logger.warning(f"AI analysis failed (non-fatal): {e}")
            return self._fallback(repo_name, findings, score)

    def _build_prompt(self, repo_name: str, findings: list[RawFinding], score: float) -> str:
        counts = {}
        for f in findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        top5 = [f"{f.scanner.upper()} [{f.severity}] {f.title}" for f in findings[:5]]
        return (
            f"Repository: {repo_name}\nScore: {score}/100\n"
            f"Findings: {json.dumps(counts)}\nTop issues:\n" +
            "\n".join(f"- {t}" for t in top5)
        )

    def _fallback(self, repo_name: str, findings: list[RawFinding], score: float) -> tuple[str, list[str]]:
        critical = sum(1 for f in findings if f.severity == "critical")
        secrets  = sum(1 for f in findings if f.scanner == "secrets")
        parts    = [f"Scan of {repo_name}: {len(findings)} issues found (score: {score}/100)."]
        if critical: parts.append(f"{critical} critical issues need immediate attention.")
        if secrets:  parts.append(f"⚠️ {secrets} secret(s) detected — rotate credentials immediately.")
        suggestions = []
        if secrets:  suggestions.append("Rotate all leaked credentials and purge them from git history.")
        if critical: suggestions.append("Fix all critical severity issues before next deployment.")
        suggestions.append("Pin GitHub Actions to full commit SHAs to prevent supply-chain attacks.")
        suggestions.append("Enable Dependabot for automated dependency updates.")
        suggestions.append("Add SAST scanning to your CI/CD pipeline.")
        return " ".join(parts), suggestions[:5]


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────


class CloneError(Exception):
    """Raised when git clone fails — no real code to scan."""


class ScanOrchestrator:
    def __init__(self, github_token: str = "", gitlab_token: str = ""):
        self.github_token = github_token
        self.gitlab_token = gitlab_token

    # ── Public API ─────────────────────────────────────────────────────────────

    async def clone(
        self,
        clone_url: str,
        branch:    str,
        scan_id:   str,
        provider:  str,
    ) -> str:
        """
        Clone the repository into a fresh temp directory.

        Returns the path to the cloned working directory on success.
        Raises CloneError with a user-readable message on any failure —
        never falls back to demo data.
        """
        work_dir   = tempfile.mkdtemp(prefix="uniops_scan_")
        authed_url = self._auth_url(clone_url, provider)

        logger.info(
            f"[scan:{scan_id}] Cloning {clone_url} "
            f"(branch={branch} provider={provider} has_token={bool(self.github_token or self.gitlab_token)})"
        )

        rc, _, stderr = await _run(
            ["git", "clone", "--depth", "1", "--branch", branch,
             "--single-branch", authed_url, work_dir],
            timeout=120,
        )

        if rc == 0:
            logger.info(f"[scan:{scan_id}] Clone successful → {work_dir}")
            return work_dir

        # Clone failed — clean up and raise a descriptive error.
        # Never fall back to synthetic data.
        shutil.rmtree(work_dir, ignore_errors=True)
        sl = stderr.lower()

        if any(k in sl for k in (
            "authentication failed", "could not read username",
            "invalid credentials", "bad credentials",
            "the requested url returned error: 403",
        )):
            raise CloneError(
                f"Authentication failed cloning {clone_url}. "
                "Go to Settings → Integrations and connect a GitHub/GitLab token "
                "with 'repo' (read) scope, then sync repositories."
            )
        if any(k in sl for k in (
            "repository not found", "not found", "does not exist",
            "the requested url returned error: 404",
        )):
            raise CloneError(
                f"Repository not found: {clone_url}. "
                "Verify the repository exists and your token has read access."
            )
        if any(k in sl for k in (
            "could not resolve host", "name or service not known",
            "network is unreachable", "connection refused",
        )):
            raise CloneError(
                f"Network error while cloning {clone_url}. "
                "Check connectivity and the repository URL."
            )
        if "remote branch" in sl and "not found" in sl:
            raise CloneError(
                f"Branch '{branch}' not found in {clone_url}. "
                "Check the branch name or leave it blank to use the default branch."
            )
        if rc == 124:
            raise CloneError(
                f"Clone timed out for {clone_url} (120 s limit). "
                "The repository may be too large or the connection too slow."
            )
        raise CloneError(
            f"git clone failed (exit {rc}) for {clone_url}: {stderr[:400]}"
        )

    async def scan_repo(
        self,
        work_dir:  str,
        scan_id:   str,
        full_name: str,
    ) -> ScanResult:
        """
        Run all security scanners on an already-cloned working directory.
        Does NOT delete work_dir — the caller is responsible for cleanup.
        """
        result   = ScanResult()
        language = self._detect_language(work_dir)
        has_docker = (Path(work_dir) / "Dockerfile").exists()
        has_cicd   = bool(CiCdScanner()._find_ci_files(work_dir))

        logger.info(
            f"[scan:{scan_id}] Starting scan — "
            f"lang={language} dockerfile={has_docker} cicd={has_cicd} "
            f"docker_available={_get_docker_available()}"
        )

        all_findings: list[RawFinding] = []

        # ── SAST + Secrets + Dependencies in parallel ──────────────────────────
        parallel_results = await asyncio.gather(
            SastScanner().run(work_dir, language),
            SecretsScanner().run(work_dir),
            DependencyScanner().run(work_dir, language),
            return_exceptions=True,
        )

        for scanner_name, res in zip(["sast", "secrets", "deps"], parallel_results):
            if isinstance(res, Exception):
                logger.warning(f"[scan:{scan_id}] {scanner_name} scanner error: {res}")
                result.scanners_run[scanner_name] = "failed"
            else:
                all_findings.extend(res)
                result.scanners_run[scanner_name] = "completed"
                result.raw_by_scanner[scanner_name] = [vars(f) for f in res[:20]]
                logger.info(f"[scan:{scan_id}] {scanner_name} → {len(res)} findings")

        # ── Container scanner (only when Dockerfile exists) ────────────────────
        if has_docker:
            try:
                cf = await ContainerScanner().run(work_dir)
                all_findings.extend(cf)
                result.scanners_run["container"] = "completed"
                result.raw_by_scanner["container"] = [vars(f) for f in cf]
                logger.info(f"[scan:{scan_id}] container → {len(cf)} findings")
            except Exception as e:
                logger.warning(f"[scan:{scan_id}] container scanner error: {e}")
                result.scanners_run["container"] = "failed"
        else:
            result.scanners_run["container"] = "skipped"
            logger.info(f"[scan:{scan_id}] container → skipped (no Dockerfile)")

        # ── CI/CD scanner (only when CI config files exist) ────────────────────
        if has_cicd:
            try:
                cf = await CiCdScanner().run(work_dir)
                all_findings.extend(cf)
                result.scanners_run["cicd"] = "completed"
                result.raw_by_scanner["cicd"] = [vars(f) for f in cf]
                logger.info(f"[scan:{scan_id}] cicd → {len(cf)} findings")
            except Exception as e:
                logger.warning(f"[scan:{scan_id}] cicd scanner error: {e}")
                result.scanners_run["cicd"] = "failed"
        else:
            result.scanners_run["cicd"] = "skipped"
            logger.info(f"[scan:{scan_id}] cicd → skipped (no CI config found)")

        result.findings = all_findings

        logger.info(
            f"[scan:{scan_id}] Scan complete — {len(all_findings)} findings | "
            f"critical={sum(1 for f in all_findings if f.severity == 'critical')} "
            f"high={sum(1 for f in all_findings if f.severity == 'high')} "
            f"medium={sum(1 for f in all_findings if f.severity == 'medium')} "
            f"low={sum(1 for f in all_findings if f.severity == 'low')}"
        )
        return result

    async def run(
        self,
        clone_url:      str,
        branch:         str,
        provider:       str,
        tenant_id:      str,
        scan_id:        str,
        repo_full_name: str,
    ) -> ScanResult:
        """
        Combined clone + scan (backward-compatible entry point).
        Raises CloneError if the repository cannot be cloned.
        The caller must NOT catch CloneError silently — let it propagate.
        """
        work_dir = await self.clone(clone_url, branch, scan_id, provider)
        try:
            return await self.scan_repo(work_dir, scan_id, repo_full_name)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
            logger.info(f"[scan:{scan_id}] Temporary clone directory removed")

    def _auth_url(self, clone_url: str, provider: str) -> str:
        if provider == "github" and self.github_token:
            return clone_url.replace("https://", f"https://{self.github_token}@")
        if provider == "gitlab" and self.gitlab_token:
            return clone_url.replace("https://", f"https://oauth2:{self.gitlab_token}@")
        return clone_url

    def _detect_language(self, repo_path: str) -> str:
        indicators = {
            "python":     ["requirements.txt", "setup.py", "pyproject.toml", "Pipfile"],
            "javascript": ["package.json"],
            "typescript": ["tsconfig.json"],
            "java":       ["pom.xml", "build.gradle"],
            "go":         ["go.mod"],
            "ruby":       ["Gemfile"],
            "rust":       ["Cargo.toml"],
            "php":        ["composer.json"],
        }
        root = Path(repo_path)
        for lang, files in indicators.items():
            if any((root / f).exists() for f in files):
                return lang
        return "unknown"

