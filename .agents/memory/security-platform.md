---
name: Security Platform Refactor
description: Architecture of the refactored 10-section Security Center DevSecOps platform
---

# Security Remediation Platform

## Navigation
- URL: `/security?section=<sectionId>` (query param, not child routes)
- 10 sections: overview, threats, vulnerabilities, compliance, repositories, assets, posture, policies, exceptions, reports

## Frontend Structure
- Main shell: `artifacts/uniops/src/pages/SecurityCenter/index.tsx` — sidebar nav + AnimatePresence section switching
- Section pages: `artifacts/uniops/src/pages/SecurityCenter/sections/` (10 files)
- API service: `artifacts/uniops/src/services/api/security.ts` — policiesApi, exceptionsApi, reportsApi, postureApi
- Old `tabs/` directory was removed

## RBAC (Frontend)
- `types/user.ts` — 11 roles: super_admin, admin, security_engineer, security_analyst, devops_engineer, compliance_manager, auditor, executive, cost_analyst, developer, viewer
- `lib/permissions.ts` — full ROLE_PERMISSIONS map + helper functions: canWriteSecurity(), canReadSecurity(), canManageCompliance()

## Backend New Models
- `security_policy.py` — SecurityPolicy (table: security_policies)
- `security_exception.py` — SecurityException (table: security_exceptions)
- `security_report.py` — SecurityReport (table: security_reports)
- `security_posture.py` — SecurityPostureScore (table: security_posture_scores)
- All registered in `models/__init__.py`

## Backend New Endpoints
- `/api/v1/security-policies` — CRUD, stats, RBAC: SecurityReadUser/SecurityWriteUser
- `/api/v1/security-exceptions` — CRUD + review workflow, RBAC: ComplianceUser for approval
- `/api/v1/security-reports` — generate + list, RBAC: AuditReadUser for list, SecurityWriteUser for generate
- `/api/v1/security-posture` — summary, history, snapshot (on-demand compute)

## Backend Services
- `security_policy_service.py`, `security_exception_service.py`, `security_report_service.py`, `security_posture_service.py`
- Posture score: weighted average — threats 30%, vulns 25%, compliance 25%, assets 10%, policies 10%

## Backend Deps (api/deps.py)
- SecurityReadUser, SecurityWriteUser, ComplianceUser, AuditReadUser — new role-scoped deps
- SECURITY_ROLES in constants/roles.py covers the 6 security-capable roles

**Why:** Tenant isolation is enforced at query level (all queries filter by tenant_id). No mock data anywhere — every component fetches from real API endpoints.
