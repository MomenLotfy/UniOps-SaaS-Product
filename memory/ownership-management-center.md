---
name: ownership-management-center
description: Ownership Management Center backend and frontend implementation
metadata:
  type: project
---

The Ownership Management Center provides comprehensive ownership tracking for all resources in the UniOps platform. It supports 25+ resource types (Repository, Organization, Project, Application, Service, Microservice, Container Image, Asset, Virtual Machine, Cloud Account, Kubernetes Cluster, Namespace, Deployment, Pod, Secret, Database, Storage Bucket, Load Balancer, Policy, Compliance Control, Exception, Threat, Vulnerability, Remediation Task, SBOM) and 9 owner types (User, Team, Department, Business Unit, Service Owner, Application Owner, Security Owner, Infrastructure Owner, Platform Team).

Backend implementation:
- `backend/app/models/ownership.py` - OwnershipMapping model with entity_type/entity_id fields for generic resource linking
- `backend/app/schemas/ownership.py` - Pydantic schemas for all API operations
- `backend/app/services/ownership_service.py` - CRUD operations and summary statistics
- `backend/app/api/v1/endpoints/ownership.py` - REST API endpoints
- `backend/alembic/versions/016_add_ownership_tables.py` - Database migration

Frontend:
- `artifacts/uniops/src/pages/SecurityCenter/sections/Ownership.tsx` - Full React dashboard with summary cards, coverage charts, search/filter, table, details drawer, owner profile modal, import/export

Key API endpoints:
- GET /ownership/summary - Summary statistics
- GET /ownership/coverage - Coverage data for charts
- GET /ownership/owner/{owner_name}/profile - Owner profile
- GET/POST/PATCH/DELETE /ownership - CRUD operations
- POST /ownership/bulk-assign - Bulk assignment
- POST /ownership/import - CSV import
- GET /ownership/export - CSV export
- GET /ownership/{type}/{id}/audit - Audit history
