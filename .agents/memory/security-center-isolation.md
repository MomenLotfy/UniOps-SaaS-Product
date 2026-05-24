---
name: Security Center Repo Isolation
description: How per-repo data isolation works in the DevSecOps Security Center — models, services, API endpoints, and frontend state.
---

## Rule
Every threat and vulnerability query MUST filter by `repo_id` to prevent data leakage across repositories within the same tenant.

## Why
Without `repo_id` on Threat/Vulnerability models and `repo_id` filters in the service layer, all findings from all repos are mixed together at tenant level. Scanning Repo A then viewing Repo B would show Repo A's threats.

## How to apply
### Backend (scan creation → storage)
- `Threat.repo_id` and `Vulnerability.repo_id` columns added (nullable, indexed) — migration `008_repo_isolation`
- `ResultAdapter.to_threats()` / `to_vulnerabilities()` in `scan_engine.py` accept `repo_id` kwarg and embed it in every record
- `_run_scan_async()` in `run_scan.py` passes `repo_id=repo_id` to ResultAdapter

### Backend (query layer)
- `SecurityService.list_threats()` / `list_vulnerabilities()` / `get_threat_stats()` / `get_vulnerability_stats()` accept optional `repo_id` and `scan_id` params — filter is applied when provided; when both are absent, all tenant data is returned (aggregate mode)
- `ScanService.get_latest_score()` / `get_scan_history()` accept optional `repo_id` — join with Repository table to return `repo_name` in scan history
- API endpoints: `/threats`, `/threats/stats`, `/vulnerabilities`, `/vulnerabilities/stats` all accept `?repo_id=` and `?scan_id=` query params
- API endpoints: `/security/score`, `/security/scan-history` both accept `?repo_id=`

### Frontend (state management)
- `selectedRepo` state is LIFTED to the parent `SecurityCenter` component (NOT local to ScanPanel)
- `ScanPanel` is a CONTROLLED component: receives `selectedRepo` + `onSelectRepo` as props
- All `useApi` paths are computed with `repo_id` appended when `selectedRepo` is set:
  - `/threats/stats?repo_id={id}`
  - `/threats?page_size=50&status=open&repo_id={id}`
  - `/vulnerabilities?page_size=50&status=open&repo_id={id}`
  - `/security/score?repo_id={id}`
  - `/security/scan-history?limit=20&repo_id={id}`
- Compliance endpoints are intentionally NOT filtered (they are tenant-wide framework scores)
- When path changes (repo switch), `useApi` immediately resets `data` to `null` (via `prevPathRef` comparison) to prevent stale data showing

### Frontend (UX cues)
- Repo context pill shown in page header subtitle when a repo is selected (with X to clear)
- "All repos" info banner shown when no repo is selected
- Summary card subtitles show the repo name
- Chart titles include the repo name
- CSV export filename includes the repo name

## Caution
- Existing threats/vulns created before migration have `repo_id = NULL` — they appear in the "all repos" aggregate view but NOT in per-repo queries. This is intentional (backward compat).
- Compliance data is intentionally tenant-wide (not repo-filtered) — frameworks are assessed across the whole org.
