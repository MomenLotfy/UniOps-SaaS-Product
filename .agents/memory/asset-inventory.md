---
name: Asset Inventory Engine
description: Architecture and gotchas for the production asset discovery system
---

# Asset Inventory Engine

## Tables
- `assets` — (tenant_id, source, external_id) unique key; upsert-safe idempotent syncs
- `asset_relationships` — directed edges: (source_asset_id, target_asset_id, relationship_type)

## Discovery Sources
- **GitHub** → `github_repo` via `GitHubClient.list_repos()`
- **GitLab** → `gitlab_repo` via `GitLabClient.list_projects()` (returns raw GitLab API JSON)
- **AWS** → `aws_ec2`, `aws_s3`, `aws_iam_user`, `aws_iam_role`, `aws_rds` via boto3 in thread pool
- **Kubernetes** → `k8s_cluster`, `k8s_namespace`, `k8s_pod` via kubernetes SDK
- **Docker** → `docker_image` extracted from existing scan raw_results (no integration needed)

## Key Gotcha: GitHub Client Owner Format
`GitHubClient.list_repos()` returns `owner` as a **string** (the login), NOT as a dict like the raw GitHub API does.
The discovery service (`_sync_github`) was fixed to handle both formats:
```python
owner_raw = repo.get("owner")
owner_login = owner_raw.get("login") if isinstance(owner_raw, dict) else owner_raw
```
**Why:** The GitHub client was designed for CI/CD use (pipelines, gitops) and simplifies the response format. Asset discovery expects the raw API shape.

## Background Scheduler
`backend/app/core/scheduler.py` — `_sync_assets` runs every 21600s (6 hours).
- Iterates all active tenants
- Opens a fresh `AsyncSessionLocal` per tenant (request session is NOT shared)
- Broadcasts `assets.synced` WebSocket event when done

## REST API (assets endpoint)
- `GET  /assets` — paginated list with filters: type, source, environment, risk_level, search, sort_by, sort_dir
- `GET  /assets/stats` — counts by type/risk/env/source
- `GET  /assets/sync/status` — last sync metadata (in-memory per tenant)
- `POST /assets/sync` — trigger full sync (all sources) as background task
- `POST /assets/sync/{source}` — trigger single-source sync
- `GET  /assets/{id}` — detail + incoming + outgoing relationships
- `PATCH /assets/{id}` — update owner/team/environment/risk_level/tags
- `DELETE /assets/{id}` — soft-delete (sets status=decommissioned)

## Frontend (Assets.tsx)
- Sortable data table with columns: Asset Name, Type, Environment, Owner, Risk Level, Last Scan, Relationships
- Slide-in detail drawer — fetches `/assets/{id}` for full relationship graph + metadata
- Stats cards: Total, Critical, High, + per-source breakdown
- Filters panel: Source pills, Risk chips, Environment dropdown, Type dropdown, per-source sync buttons
- Sync status polls every 3s while running; broadcasts via WebSocket on completion
- Empty state guides user to connect integrations + sync

**Why real only:** No mock data anywhere. Empty state explicitly tells user to connect integrations.
