---
name: Repository Risk Rating Engine
description: Risk scoring for repos after each scan — model, service, API, scan hook, frontend
---

## Risk Score Formula (0-100, higher = more risky)
- Critical findings: +18 each, cap 54
- High findings:    +7 each,  cap 35
- Secrets:          +12 each, cap 36
- Container issues: +5 each,  cap 25
- Compliance violations: +6 each, cap 24
- Exposure risk:    +5 (public), +15 (never scanned), +10 (>30 days), +3 (>7 days)

Risk Level thresholds: critical≥75, high≥50, medium≥25, low<25
Trend: worsening if score went up >5, improving if down >5, else stable

## Key files
- Model: `backend/app/models/repository_risk.py` — `repository_risk_scores` table
- Service: `backend/app/services/risk_service.py` — RiskService.compute_and_store(), list_risk_ratings(), get_risk_rating()
- API: `backend/app/api/v1/endpoints/repository_risk.py` — GET /repos/risk, GET /repos/risk/{repo_id}
- Scan hook: `backend/app/tasks/run_scan.py` — called after SBOM generation, non-fatal
- Frontend: `artifacts/uniops/src/pages/SecurityCenter/sections/Repositories.tsx`

## Design decisions
- Upsert pattern (not insert): one risk record per repo, updated on each scan
- Sorted by risk_score DESC from the API (critical repos first)
- compliance_violations = sum of all Compliance.failed across frameworks for tenant
- Exposure risk currently treats all repos as private (is_private flag used)
- Risk computation re-fetches scan+repo post-commit to avoid stale ORM state

## Frontend Repositories.tsx features
- Risk summary bar (4 clickable cards: critical/high/medium/low counts)
- Risk filter + provider filter
- Each row: colored left stripe, RiskBadge, trend icon, security score bar, open findings count
- Expandable drill-down: factor pills + score progression vs previous
- Repo dropdown in scanner panel shows risk badge inline
- Sorted by risk level (critical first), then risk_score

**Why:** repos with most critical risk should always appear at top for immediate attention.
