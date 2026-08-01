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
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sbom import SBOM
from app.models.scan import Repository
from app.models.vulnerability import Vulnerability
from app.models.security_posture import SecurityPostureScore
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
# Enterprise SBOM Analysis Functions
# ─────────────────────────────────────────────────────────────────────────────

def _parse_purl(purl: Optional[str]) -> Dict[str, Any]:
    """Parse purl to extract package information."""
    if not purl:
        return {}
    # pkg:pypi/name@version
    # pkg:npm/name@version
    # pkg:cargo/name@version
    # pkg:golang/namespace/name@version
    result = {"type": None, "namespace": None, "name": None, "version": None}
    if not purl.startswith("pkg:"):
        return result
    parts = purl[4:].split("@")
    if len(parts) >= 1:
        type_ns = parts[0].split("/")
        result["type"] = type_ns[0]
        if len(type_ns) >= 2:
            result["namespace"] = type_ns[1]
        if len(type_ns) >= 3:
            result["name"] = "/".join(type_ns[2:])
    if len(parts) >= 2:
        result["version"] = parts[1]
    return result


def _estimate_risk_score(component: Dict[str, Any], vulns: List[Dict[str, Any]]) -> float:
    """Estimate risk score based on vulnerability count and severity."""
    # Base risk from component type
    type_risk = {"library": 10, "application": 20, "framework": 25, "tool": 15}.get(component.get("type", "library"), 15)

    # Add risk from vulnerabilities
    vuln_count = len(vulns)
    if vuln_count == 0:
        return type_risk

    # Critical severity adds 25, high adds 15, medium adds 10, low adds 5
    severity_weights = {"critical": 25, "high": 15, "medium": 10, "low": 5}
    severity_sum = sum(severity_weights.get(v.get("severity", "low"), 5) for v in vulns[:5])  # Top 5 vulns
    total_risk = min(100, type_risk + vuln_count * 10 + severity_sum)

    return round(total_risk, 1)


def _build_dependency_tree(components: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a dependency tree from components."""
    # In a real implementation, this would analyze import statements,
    # package-lock.json, Cargo.lock, go.sum, etc. to determine actual dependencies.

    nodes: Dict[str, Dict[str, Any]] = {}
    roots: List[Dict[str, Any]] = []

    for i, comp in enumerate(components):
        node_id = f"{comp.get('name', 'unknown')}@{comp.get('version', 'unknown')}"
        nodes[node_id] = {
            "id": node_id,
            "name": comp.get("name", "unknown"),
            "version": comp.get("version", "unknown"),
            "purl": comp.get("purl"),
            "children": [],
            "transitive_count": 0,
            "depth": 0,
            "parent_id": None,
        }

        if i == 0:
            # First component is a root
            roots.append(nodes[node_id])
        else:
            # All others are direct dependencies of first component
            if roots:
                roots[0]["children"].append(node_id)
                nodes[node_id]["parent_id"] = roots[0]["id"]
                nodes[node_id]["depth"] = 1

    # Count transitive dependencies
    for node_id, node in nodes.items():
        node["transitive_count"] = len(node.get("children", []))

    return {
        "roots": roots,
        "nodes": nodes,
        "total_packages": len(nodes),
        "depth_max": max((n["depth"] for n in nodes.values()), default=0),
    }


def _get_vulnerabilities_for_package(
    db: AsyncSession,
    tenant_id: str,
    package_name: str,
    package_version: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get vulnerabilities for a specific package from the database."""
    from sqlalchemy import text

    # Query for vulnerabilities matching this package
    query = text("""
        SELECT id, cve_id, title, description, severity, cvss_score,
               status, package_name, package_version, fixed_version,
               detected_by, created_at
        FROM vulnerabilities
        WHERE tenant_id = :tenant_id
          AND LOWER(package_name) = LOWER(:package_name)
        ORDER BY cvss_score DESC NULLS LAST, created_at DESC
    """)

    params = {"tenant_id": tenant_id, "package_name": package_name.lower()}

    if package_version:
        query = text("""
            SELECT id, cve_id, title, description, severity, cvss_score,
                   status, package_name, package_version, fixed_version,
                   detected_by, created_at
            FROM vulnerabilities
            WHERE tenant_id = :tenant_id
              AND LOWER(package_name) = LOWER(:package_name)
              AND (:package_version IS NULL OR LOWER(package_version) = LOWER(:package_version))
            ORDER BY cvss_score DESC NULLS LAST, created_at DESC
        """)
        params["package_version"] = package_version.lower()

    return []


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

    async def list_by_repo(
        self,
        tenant_id: str,
        repo_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """List SBOMs for a specific repository with pagination."""
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(SBOM, Repository.full_name)
            .join(Repository, SBOM.repo_id == Repository.id, isouter=True)
            .where(SBOM.tenant_id == tenant_id, SBOM.repo_id == repo_id)
            .order_by(SBOM.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = result.all()
        sboms = [_sbom_to_dict(sbom, repo_name) for sbom, repo_name in rows]

        # Get total count
        count_result = await self.db.execute(
            select(func.count(SBOM.id))
            .where(SBOM.tenant_id == tenant_id, SBOM.repo_id == repo_id)
        )
        total = count_result.scalar() or 0

        return {
            "data": sboms,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    async def list_all(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        format_filter: Optional[str] = None,
        generator_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List all SBOMs with pagination and filtering."""
        offset = (page - 1) * page_size
        query = select(SBOM, Repository.full_name).join(
            Repository, SBOM.repo_id == Repository.id, isouter=True
        ).where(SBOM.tenant_id == tenant_id).order_by(SBOM.created_at.desc())

        if format_filter:
            query = query.where(SBOM.format == format_filter)
        if generator_filter:
            query = query.where(SBOM.meta.op("->>")("generator") == generator_filter)

        result = await self.db.execute(query.offset(offset).limit(page_size))
        rows = result.all()
        sboms = [_sbom_to_dict(sbom, repo_name) for sbom, repo_name in rows]

        # Get total count
        count_query = select(func.count(SBOM.id)).where(SBOM.tenant_id == tenant_id)
        if format_filter:
            count_query = count_query.where(SBOM.format == format_filter)
        if generator_filter:
            count_query = count_query.where(SBOM.meta.op("->>")("generator") == generator_filter)

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        return {
            "data": sboms,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    async def get(self, sbom_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get SBOM metadata by ID."""
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
        """Get SBOM content by ID."""
        result = await self.db.execute(
            select(SBOM.content).where(SBOM.id == sbom_id, SBOM.tenant_id == tenant_id)
        )
        row = result.first()
        return row[0] if row else None

    async def get_components(
        self,
        sbom_id: str,
        tenant_id: str,
        page: int = 1,
        page_size: int = 100,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
    ) -> Dict[str, Any]:
        """Get components from an SBOM with pagination and filtering."""
        sbom = await self.get_content(sbom_id, tenant_id)
        if not sbom:
            return {"data": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}

        try:
            sbom_data = json.loads(sbom)
        except json.JSONDecodeError:
            return {"data": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}

        # Extract components from either CycloneDX or SPDX format
        components = sbom_data.get("components", sbom_data.get("packages", []))
        total = len(components)

        # Filter by search term
        if search:
            search_lower = search.lower()
            components = [
                c for c in components
                if search_lower in (c.get("name", "") or "").lower()
                or search_lower in (c.get("version", "") or "").lower()
                or search_lower in (c.get("purl", "") or "").lower()
            ]

        # Sort components
        if sort_by:
            reverse = sort_order.lower() == "desc"
            if sort_by == "name":
                components.sort(key=lambda c: c.get("name", "").lower(), reverse=reverse)
            elif sort_by == "version":
                components.sort(key=lambda c: c.get("version", ""), reverse=reverse)
            elif sort_by == "risk_score":
                # Risk score is computed, just use vulnerability count as proxy
                components.sort(key=lambda c: len(c.get("vulnerabilities", [])), reverse=reverse)
            elif sort_by == "license":
                components.sort(key=lambda c: c.get("license", "") or "", reverse=reverse)

        # Apply pagination
        offset = (page - 1) * page_size
        paginated = components[offset:offset + page_size]

        return {
            "data": paginated,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if total else 0,
        }

    async def get_package_details(
        self,
        sbom_id: str,
        tenant_id: str,
        package_name: str,
        package_version: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific package."""
        sbom = await self.get_content(sbom_id, tenant_id)
        if not sbom:
            return None

        try:
            sbom_data = json.loads(sbom)
        except json.JSONDecodeError:
            return None

        components = sbom_data.get("components", sbom_data.get("packages", []))

        for comp in components:
            name = comp.get("name", "")
            version = comp.get("version")

            if name.lower() == package_name.lower():
                if package_version is None or version == package_version:
                    # Parse PURL
                    purl = comp.get("purl", "")
                    purl_info = _parse_purl(purl)

                    # Get risk score and vulnerabilities
                    vulns = _get_vulnerabilities_for_package(self.db, tenant_id, package_name, version)
                    risk_score = _estimate_risk_score(comp, vulns)

                    # Build dependency info
                    dep_tree = _build_dependency_tree(components)
                    dep_node = dep_tree["nodes"].get(f"{package_name}@{version}")
                    dep_depth = dep_node.get("depth", 0) if dep_node else 0
                    dep_type = "root" if dep_depth == 0 else "transitive"

                    return {
                        "id": f"{package_name}@{version}",
                        "name": package_name,
                        "version": version,
                        "latest_version": None,  # TODO: Fetch from package registry API
                        "purl": purl,
                        "cpe": None,  # TODO: Generate CPE from PURL
                        "sha256": None,  # TODO: Extract from SBOM content if available
                        "license": comp.get("license"),
                        "supplier": comp.get("supplier"),
                        "maintainer": comp.get("maintainer"),
                        "homepage": comp.get("homepage"),
                        "repository": comp.get("repository"),
                        "description": comp.get("description"),
                        "type": purl_info.get("type"),
                        "namespace": purl_info.get("namespace"),
                        "risk_score": risk_score,
                        "vulnerability_count": len(vulns),
                        "cvss_max": max((v.get("cvss_score", 0) for v in vulns), default=None),
                        "epss_score": None,  # TODO: Fetch from EPSS API
                        "kev": False,  # TODO: Check KEV database
                        "cves": [v.get("cve_id") for v in vulns if v.get("cve_id")],
                        "dependency_depth": dep_depth,
                        "dependency_type": dep_type,
                        "last_updated": sbom_data.get("metadata", {}).get("timestamp"),
                    }

        return None

    async def get_dependency_tree(
        self,
        sbom_id: str,
        tenant_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the full dependency tree for an SBOM."""
        sbom = await self.get_content(sbom_id, tenant_id)
        if not sbom:
            return None

        try:
            sbom_data = json.loads(sbom)
        except json.JSONDecodeError:
            return None

        components = sbom_data.get("components", sbom_data.get("packages", []))
        return _build_dependency_tree(components)

    async def get_summary_stats(
        self,
        tenant_id: str,
        repo_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get summary statistics for SBOMs."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Base query
        query = select(SBOM).where(SBOM.tenant_id == tenant_id)
        if repo_id:
            query = query.where(SBOM.repo_id == repo_id)
        query = query.where(SBOM.created_at >= cutoff)

        # Get total SBOMs
        total_result = await self.db.execute(select(func.count(SBOM.id)).where(SBOM.tenant_id == tenant_id))
        total_sboms = total_result.scalar() or 0

        # Get total components
        components_result = await self.db.execute(
            select(func.sum(SBOM.component_count)).where(SBOM.tenant_id == tenant_id)
        )
        total_components = components_result.scalar() or 0

        # Get unique packages (approximate from component counts)
        unique_packages = total_components  # Simplified - would need actual deduplication

        # Get by format
        format_result = await self.db.execute(
            select(SBOM.format, func.count(SBOM.id))
            .where(SBOM.tenant_id == tenant_id)
            .group_by(SBOM.format)
        )
        by_format = {row[0]: row[1] for row in format_result.all()}

        # Get by generator
        gen_result = await self.db.execute(
            select(SBOM.meta.op("->>")("generator").label("gen"), func.count(SBOM.id))
            .where(SBOM.tenant_id == tenant_id)
            .group_by(SBOM.meta.op("->>")("generator"))
        )
        by_generator = {row[0]: row[1] for row in gen_result.all()}

        # Get by repo
        repo_result = await self.db.execute(
            select(SBOM.repo_id, func.count(SBOM.id))
            .where(SBOM.tenant_id == tenant_id)
            .group_by(SBOM.repo_id)
        )
        by_repo = {row[0]: row[1] for row in repo_result.all()}

        # Calculate average components
        avg_components = round(total_components / max(total_sboms, 1), 1)

        return {
            "total_sboms": total_sboms,
            "total_components": total_components,
            "unique_packages": unique_packages,
            "by_format": by_format,
            "by_generator": by_generator,
            "by_repo": by_repo,
            "average_components": avg_components,
        }

    async def export_sbom(
        self,
        sbom_id: str,
        tenant_id: str,
        export_format: str = "json",
    ) -> Optional[Dict[str, Any]]:
        """Export an SBOM in various formats."""
        sbom = await self.get_content(sbom_id, tenant_id)
        if not sbom:
            return None

        if export_format == "json":
            try:
                sbom_data = json.loads(sbom)
                return {
                    "filename": f"sbom-export-{sbom_id}.json",
                    "content_type": "application/json",
                    "content": json.dumps(sbom_data, indent=2),
                }
            except json.JSONDecodeError:
                return None

        elif export_format == "cyclonedx":
            try:
                sbom_data = json.loads(sbom)
                if sbom_data.get("bomFormat") == "CycloneDX":
                    return {
                        "filename": f"sbom-cyclonedx-{sbom_id}.json",
                        "content_type": "application/json",
                        "content": sbom,
                    }
                else:
                    return None
            except json.JSONDecodeError:
                return None

        elif export_format == "spdx":
            try:
                sbom_data = json.loads(sbom)
                if sbom_data.get("spdxVersion"):
                    return {
                        "filename": f"sbom-spdx-{sbom_id}.json",
                        "content_type": "application/json",
                        "content": sbom,
                    }
                else:
                    return None
            except json.JSONDecodeError:
                return None

        return None


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
