---
name: Epic 9 Integration Layer
description: Key lessons from implementing the real Kubernetes/Prometheus/Loki/ArgoCD integration layer
---

## DB session import
Use `from app.core.database import AsyncSessionLocal` — there is no `async_session_factory`.
Context manager: `async with AsyncSessionLocal() as session:`.

**Why:** The database module exports `AsyncSessionLocal` (sqlalchemy async_sessionmaker), not a factory function.

**How to apply:** Any new file that needs a standalone DB session (outside a request context) must use this pattern.

## from __future__ imports
A file can only have ONE `from __future__ import annotations` line and it must be the first statement (before the docstring comment is fine, but only one occurrence). Duplicate `from __future__` at any later line causes a Python SyntaxError that surfaces as a non-fatal warning in the lifespan handler but silently skips the module.

**Why:** Python's grammar requires future imports at the start of the file, exactly once.

**How to apply:** Always check new integration files for accidental double-import before saving.

## Event bus startup
`event_bus.enable_ws_bridge()` must be called exactly once at startup (in lifespan). It registers the wildcard WS handler. Calling twice doubles all events to connected clients.

**How to apply:** In `main.py` lifespan step 5, one call only.

## K8s watcher bootstrap
`bootstrap_watchers()` runs as a background task — any failure is non-fatal (logged as `[k8s_watcher] bootstrap_watchers skipped`). When no clusters have status='connected' in the DB it exits immediately and gracefully.

## Integration detection pattern (metrics/logs/gitops endpoints)
All new endpoints follow: try live integration client → fallback to K8s snapshot → fallback to synthetic/DB data. The `source` field in the response tells the client which tier was used.
