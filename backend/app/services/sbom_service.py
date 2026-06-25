from __future__ import annotations
"""
SBOM Service
============
Generates Software Bill of Materials (SBOM) for scanned repositories.

Strategy:
  1. Try Syft binary (if installed) — produces CycloneDX JSON.
  2. Fallback: parse manifest files directly (requirements.txt, package.json,
     Cargo.toml, go.mod, pom.xml, Gemfile) and build CycloneDX + SPDX JSON
     from the package list — works in any environment, no Docker needed.

Always stores metadata in PostgreSQL.  Content (full JSON) is stored as text
in the `sboms.content` column so download endpoints can serve it.
"""
import asyncio
import json
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sbom import SBOM
from app.models.scan import Repository
from app.utils.logger import logger


# ─────────────────────────────────────────────────────────────────────────────
# Manifest parsers — lightweight, no external tools
# ─────────────────────────────────────────────────────────────────────────────

def _parse_requirements_txt(path: Path) -> list[dict]:
    components = []
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)\s*[=<>!~]{1,2}\s*([^\s;#]+)", line)
        if m:
            components.append({"type": "library", "name": m.group(1), "version": m.group(2), "purl": f"pkg:pypi/{m.group(1).lower()}@{m.group(2)}"})
        else:
            name = re.split(r"[=<>!~\s;#]", line)[0].strip()
            if name:
                components.append({"type": "library", "name": name, "version": "unknown", "purl": f"pkg:pypi/{name.lower()}"})
    return components


def _parse_package_json(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(errors="replace"))
    except Exception:
        return []
    components = []
    for section in ("dependencies", "devDependencies"):
        for name, version in (data.get(section) or {}).items():
            ver = str(version).lstrip("^~>=<")
            components.append({"type": "library", "name": name, "version": ver, "purl": f"pkg:npm/{name}@{ver}"})
    return components


def _parse_cargo_toml(path: Path) -> list[dict]:
    components = []
    in_deps = False
    for line in path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped in ("[dependencies]", "[dev-dependencies]", "[build-dependencies]"):
            in_deps = True
            continue
        if stripped.startswith("["):
            in_deps = False
            continue
        if in_deps:
            m = re.match(r'^([A-Za-z0-9_\-]+)\s*=\s*["\']([^"\']+)["\']', stripped)
            if m:
                components.append({"type": "library", "name": m.group(1), "version": m.group(2), "purl": f"pkg:cargo/{m.group(1)}@{m.group(2)}"})
    return components


def _parse_go_mod(path: Path) -> list[dict]:
    components = []
    in_require = False
    for line in path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped == "require (":
            in_require = True
            continue
        if stripped == ")":
            in_require = False
            continue
        if in_require or stripped.startswith("require "):
            part = stripped.removeprefix("require ").strip()
            parts = part.split()
            if len(parts) >= 2:
                name, ver = parts[0], parts[1]
                components.append({"type": "library", "name": name, "version": ver, "purl": f"pkg:golang/{name}@{ver}"})
    return components


def _parse_gemfile(path: Path) -> list[dict]:
    components = []
    for line in path.read_text(errors="replace").splitlines():
        m = re.match(r"""^\s*gem\s+['"]([^'"]+)['"](?:\s*,\s*['"]([^'"]+)['"])?""", line)
        if m:
            name = m.group(1)
            version = m.group(2) or "unknown"
            components.append({"type": "library", "name": name, "version": version, "purl": f"pkg:gem/{name}@{version}"})
    return components


def _collect_components(repo_path: str) -> list[dict]:
    """Scan known manifest files and collect all components."""
    root = Path(repo_path)
    components: list[dict] = []

    manifests = {
        "requirements.txt": _parse_requirements_txt,
        "package.json":     _parse_package_json,
        "Cargo.toml":       _parse_cargo_toml,
        "go.mod":           _parse_go_mod,
        "Gemfile":          _parse_gemfile,
    }

    for filename, parser in manifests.items():
        fpath = root / filename
        if fpath.exists():
            try:
                found = parser(fpath)
                components.extend(found)
                logger.debug(f"[sbom] {filename} → {len(found)} components")
            except Exception as e:
                logger.warning(f"[sbom] failed to parse {filename}: {e}")

    # Deduplicate by (name, version)
    seen: set[tuple] = set()
    unique: list[dict] = []
    for c in components:
        key = (c["name"], c["version"])
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return unique


# ─────────────────────────────────────────────────────────────────────────────
# SBOM format builders
# ─────────────────────────────────────────────────────────────────────────────

def _build_cyclonedx(components: list[dict], repo_name: str, scan_id: Optional[str]) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "bomFormat":   "CycloneDX",
        "specVersion": "1.4",
        "version":     1,
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "metadata": {
            "timestamp": now,
            "tools": [{"vendor": "UniOps", "name": "Security Scanner", "version": "1.0"}],
            "component": {"type": "application", "name": repo_name, "bom-ref": scan_id or repo_name},
        },
        "components": [
            {
                "type":    c["type"],
                "name":    c["name"],
                "version": c["version"],
                "purl":    c.get("purl", ""),
                "bom-ref": f"{c['name']}@{c['version']}",
            }
            for c in components
        ],
    }


def _build_spdx(components: list[dict], repo_name: str, scan_id: Optional[str]) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    packages = []
    for i, c in enumerate(components):
        packages.append({
            "SPDXID":              f"SPDXRef-Package-{i}",
            "name":                c["name"],
            "versionInfo":         c["version"],
            "downloadLocation":    "NOASSERTION",
            "filesAnalyzed":       False,
            "externalRefs": [
                {"referenceCategory": "PACKAGE_MANAGER", "referenceType": "purl", "referenceLocator": c.get("purl", "")}
            ] if c.get("purl") else [],
        })
    return {
        "SPDXID":           "SPDXRef-DOCUMENT",
        "spdxVersion":      "SPDX-2.3",
        "creationInfo": {
            "created":  now,
            "creators": ["Tool: UniOps Security Scanner"],
        },
        "name":             f"SBOM-{repo_name}",
        "dataLicense":      "CC0-1.0",
        "documentNamespace": f"https://uniops.io/sbom/{scan_id or uuid.uuid4()}",
        "packages":         packages,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Syft integration (optional — uses binary if available)
# ─────────────────────────────────────────────────────────────────────────────

def _syft_available() -> bool:
    return bool(shutil.which("syft"))


async def _run_syft(repo_path: str, fmt: str) -> Optional[dict]:
    """Run Syft and return parsed JSON output, or None on failure."""
    syft_fmt = "cyclonedx-json" if fmt == "cyclonedx" else "spdx-json"
    try:
        proc = await asyncio.create_subprocess_exec(
            "syft", repo_path, "-o", syft_fmt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode == 0:
            return json.loads(stdout.decode(errors="replace"))
    except Exception as e:
        logger.warning(f"[sbom] Syft failed: {e}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# SBOMService
# ─────────────────────────────────────────────────────────────────────────────

class SBOMService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate(
        self,
        repo_path: str,
        tenant_id: str,
        repo_id:   str,
        scan_id:   Optional[str],
        repo_name: str,
    ) -> list[SBOM]:
        """
        Generate CycloneDX + SPDX SBOMs for the given repository clone.
        Stores both records in PostgreSQL and returns them.
        Never raises — on failure, logs a warning and returns empty list.
        """
        logger.info(f"[sbom] Generating SBOMs for repo={repo_name} scan={scan_id}")

        # 1. Collect components (Syft → manifest fallback)
        components: list[dict] = []
        if _syft_available():
            syft_result = await _run_syft(repo_path, "cyclonedx")
            if syft_result:
                components = syft_result.get("components", [])
                logger.info(f"[sbom] Syft found {len(components)} components")

        if not components:
            components = _collect_components(repo_path)
            logger.info(f"[sbom] Manifest parser found {len(components)} components")

        if not components:
            logger.info(f"[sbom] No components found for repo={repo_name} — skipping SBOM generation")
            return []

        records: list[SBOM] = []
        now = datetime.now(timezone.utc)

        for fmt, builder in [("cyclonedx", _build_cyclonedx), ("spdx", _build_spdx)]:
            try:
                content_dict = builder(components, repo_name, scan_id)
                content_str  = json.dumps(content_dict, indent=2)
                sbom = SBOM(
                    tenant_id=tenant_id,
                    repo_id=repo_id,
                    scan_id=scan_id,
                    format=fmt,
                    component_count=len(components),
                    content=content_str,
                    meta={
                        "repo_name":        repo_name,
                        "generated_at":     now.isoformat(),
                        "generator":        "syft" if _syft_available() and components else "manifest-parser",
                        "component_count":  len(components),
                    },
                )
                self.db.add(sbom)
                records.append(sbom)
                logger.info(f"[sbom] Created {fmt} SBOM with {len(components)} components")
            except Exception as e:
                logger.warning(f"[sbom] Failed to create {fmt} SBOM: {e}")

        if records:
            await self.db.commit()
            for r in records:
                await self.db.refresh(r)

        return records

    async def list_by_repo(self, tenant_id: str, repo_id: str) -> list[dict]:
        result = await self.db.execute(
            select(SBOM, Repository.full_name)
            .join(Repository, SBOM.repo_id == Repository.id, isouter=True)
            .where(SBOM.tenant_id == tenant_id, SBOM.repo_id == repo_id)
            .order_by(SBOM.created_at.desc())
        )
        rows = result.all()
        return [_sbom_to_dict(sbom, repo_name) for sbom, repo_name in rows]

    async def list_all(self, tenant_id: str) -> list[dict]:
        result = await self.db.execute(
            select(SBOM, Repository.full_name)
            .join(Repository, SBOM.repo_id == Repository.id, isouter=True)
            .where(SBOM.tenant_id == tenant_id)
            .order_by(SBOM.created_at.desc())
            .limit(200)
        )
        rows = result.all()
        return [_sbom_to_dict(sbom, repo_name) for sbom, repo_name in rows]

    async def get(self, sbom_id: str, tenant_id: str) -> Optional[dict]:
        result = await self.db.execute(
            select(SBOM, Repository.full_name)
            .join(Repository, SBOM.repo_id == Repository.id, isouter=True)
            .where(SBOM.id == sbom_id, SBOM.tenant_id == tenant_id)
        )
        row = result.first()
        if not row:
            return None
        sbom, repo_name = row
        return _sbom_to_dict(sbom, repo_name)

    async def get_content(self, sbom_id: str, tenant_id: str) -> Optional[str]:
        result = await self.db.execute(
            select(SBOM.content).where(SBOM.id == sbom_id, SBOM.tenant_id == tenant_id)
        )
        row = result.first()
        return row[0] if row else None


def _sbom_to_dict(sbom: SBOM, repo_name: Optional[str] = None) -> dict:
    meta = sbom.meta or {}
    return {
        "id":              sbom.id,
        "tenant_id":       sbom.tenant_id,
        "repo_id":         sbom.repo_id,
        "repo_name":       repo_name or meta.get("repo_name", ""),
        "scan_id":         sbom.scan_id,
        "format":          sbom.format,
        "component_count": sbom.component_count,
        "generated_at":    meta.get("generated_at", sbom.created_at.isoformat()),
        "generator":       meta.get("generator", ""),
        "created_at":      sbom.created_at.isoformat(),
    }
