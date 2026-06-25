---
name: SBOM + Vulnerability Deduplication Engine
description: Phase 1 Step 4 implementation details — SBOM generation, dedup engine, frontend sections
---

## SBOM Generation
- `sboms` table: tenant_id, repo_id, scan_id, format (cyclonedx/spdx), component_count, content (Text), meta (JSON)
- SBOMService in `backend/app/services/sbom_service.py` — Syft binary if available, otherwise parses manifests (requirements.txt, package.json, Cargo.toml, go.mod, Gemfile)
- Both CycloneDX 1.4 and SPDX 2.3 formats always generated per scan
- Hooked into run_scan.py AFTER `await db.commit()` on scan completion — non-fatal (warns on failure)
- 3 endpoints: GET /api/v1/sbom, GET /api/v1/sbom/{id}, GET /api/v1/sbom/{id}/download

## Vulnerability Deduplication
- Dedup key: (tenant_id, cve_id, package_name) — only fires when both cve_id AND package_name are non-null
- New columns: detected_by (JSON list), first_seen_at (TIMESTAMPTZ), last_seen_at (TIMESTAMPTZ)
- `scanner_name` field added to vuln dicts from ResultAdapter.to_vulnerabilities — consumed by _upsert_vulnerability in run_scan.py, NOT stored directly (stripped before Vulnerability(**vd))
- On merge: appends scanner to detected_by list, updates last_seen_at and scan_id to current scan
- On new: sets first_seen_at = last_seen_at = now, detected_by = [scanner_name]

## Critical SQLAlchemy Gotcha
SQLAlchemy `create_all` creates NEW tables but does NOT alter existing tables to add columns.
When adding columns to an existing model, must run ALTER TABLE manually:
```sql
ALTER TABLE vulnerabilities
ADD COLUMN IF NOT EXISTS detected_by JSON DEFAULT '[]'::json,
ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ
```

**Why:** create_all checks if table exists (it does) and skips it entirely. No Alembic is configured in this project.

## Frontend
- New section: `artifacts/uniops/src/pages/SecurityCenter/sections/SBOM.tsx`
- Updated: `Vulnerabilities.tsx` shows detected_by scanner badges + first_seen_at/last_seen_at date range
- SecurityCenter index.tsx: added `sbom` to SecuritySection union type, NAV_ITEMS, SECTION_COMPONENTS
