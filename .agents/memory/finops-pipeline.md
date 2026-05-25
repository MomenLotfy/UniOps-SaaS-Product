---
name: FinOps Cost Center Pipeline Fixes
description: Lessons from fixing the AWS cost data pipeline — backend async, frontend polling, and empty states.
---

## The rule
All boto3 calls must be wrapped in `asyncio.get_event_loop().run_in_executor(None, fn)` — they are blocking and will stall the FastAPI event loop otherwise.

**Why:** AWS Cost Explorer API calls can take 5–30 seconds. Running them directly in an async route/task handler freezes the entire server.

**How to apply:** Any time you add a new boto3 call (Cost Explorer, STS, EC2, etc.), wrap it in run_in_executor before awaiting.

## Frontend polling strategy
A fixed 5-second `setTimeout → invalidateQueries` is too short for AWS CE API. Use a smart poll loop:
- First poll after 10 seconds (give CE time to respond)
- Then every 5 seconds for up to 90 seconds (18 attempts)
- Stop when `has_data=true` OR `last_sync` changes
- Fall back to a final invalidation on timeout

**Why:** AWS CE typically responds in 10–30 seconds. A 5s fixed delay caused the frontend to re-fetch before any data was written.

## Auto-sync on first connect
Use `useRef(false)` guard + `useEffect` watching `summaryQ.data` to auto-trigger sync when:
- `integration_status === 'connected'` (or `sync_failed`)
- `has_data === false`
- No sync is already pending

This removes the need for the user to manually click "Sync Now" after connecting AWS.

**Why:** Users expect data to appear automatically after connecting an integration.

## has_data / has_integration flags
`GET /costs/summary` returns `has_integration: bool` and `has_data: bool`:
- `has_integration=false` → show NotConnectedBanner (no AWS record at all)
- `has_integration=true, has_data=false` → show inline "no data yet" strip + auto-sync
- `has_data=true` → show full dashboard with real metrics

**Why:** The old code showed an empty dashboard when connected but never synced — confusing.
