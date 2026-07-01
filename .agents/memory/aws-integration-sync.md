---
name: AWS Integration Full Sync Fix
description: After connecting AWS, the background task must trigger all four sync steps, not just costs.
---

## Rule
After AWS credentials are verified (STS OK), the background tasks `_bg_test_and_sync` and `_bg_sync` must run all four steps in order:
1. `sync_aws_costs_async(tenant_id)` — Cost Explorer → cost_metrics table
2. `AssetDiscoveryService.sync_all(tenant_id)` — EC2/S3/IAM/RDS → assets table
3. `sync_aws_security_async(tenant_id)` — Security Hub → threats/vulnerabilities tables
4. `SecurityPostureService.record_snapshot(tenant_id)` — recompute posture scores

**Why:** The original code only ran step 1, so Security Center showed no AWS data until the 6-hourly scheduler fired. Users expected immediate data after connecting.

**How to apply:** Both `_bg_test_and_sync` (fires on connect) and `_bg_sync` (fires on "Sync Now") in `backend/app/api/v1/endpoints/integrations.py` must call all four steps. Each step is wrapped in its own try/except so one failure doesn't abort the rest.

**Method name:** Use `record_snapshot()` not `take_snapshot()` — the SecurityPostureService method is `record_snapshot`.

**IAM permissions needed:** ReadOnlyAccess + SecurityAudit (covers EC2, S3, IAM, RDS describe + Security Hub read).
