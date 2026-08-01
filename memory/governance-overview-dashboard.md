---
name: governance-overview-dashboard
description: Governance Overview executive dashboard implementation
metadata:
  type: project
---

The Governance Overview Dashboard provides an executive-level view of security posture with comprehensive metrics and analytics.

Backend implementation:
- `backend/app/schemas/governance_overview.py` - Pydantic schemas for governance overview, health indicators, risk distribution, compliance, SLA, remediation, threat intelligence, executive timeline, business impact
- `backend/app/services/governance_overview_service.py` - GovernanceOverviewService with methods for computing scores, building summaries, health indicators, risk distribution, ownership summary, SLA summary, remediation overview, compliance overview, policy overview, threat intelligence, executive timeline, and business impact analysis
- `backend/app/api/v1/endpoints/governance_overview.py` - REST API endpoints

Frontend:
- `artifacts/uniops/src/pages/SecurityCenter/sections/GovernanceOverview.tsx` - Full React dashboard with:
  - Executive KPI cards (Overall Security Score, Governance Score, Compliance %, Risk Score, Open Findings, Critical Findings, Breached SLAs, Open Exceptions, Remediation Progress %, Policy Violations, Protected Assets %, Repositories Covered %, Average MTTR)
  - Health indicators grid for all resource types (Repository, Infrastructure, Cloud Account, Kubernetes Cluster, Application, Service, Asset)
  - Risk distribution charts (by severity, environment)
  - Compliance and Policy overview cards
  - Threat intelligence section
  - SLA summary with compliance rate
  - Executive timeline with events
  - Business impact analysis
  - Export functionality (JSON, CSV, Excel)

Key API endpoints:
- GET /governance/overview - Full governance overview with all data
- GET /governance/summary - Summary KPIs for cards
- GET /governance/health - Health indicators for all resource types
- GET /governance/risk - Risk distribution data
- GET /governance/ownership-summary - Ownership summary
- GET /governance/sla-summary - SLA summary
- GET /governance/remediation - Remediation overview
- GET /governance/compliance - Compliance overview
- GET /governance/policy - Policy overview
- GET /governance/threats - Threat intelligence
- GET /governance/timeline - Executive timeline
- GET /governance/business-impact - Business impact analysis
- POST /governance/export - Export data in specified format
