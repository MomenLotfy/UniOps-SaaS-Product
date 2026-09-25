---
name: Async worker test sessions
description: Safe verification pattern for background workers that commit through a separate SQLAlchemy async session.
---

When an async worker is tested with a separate database session, capture identifiers before the worker runs and use fresh queries with explicit refresh/populate behavior afterward. Do not expire objects in the original `AsyncSession` and then access their attributes.

SQLite drops timezone information when loading `DateTime(timezone=True)` values. Before comparing a loaded naive timestamp with an aware UTC timestamp, attach UTC to the loaded value; otherwise worker code can raise `TypeError` and silently skip non-fatal policy evaluation.

**Why:** The original test session may hold stale identity-map state, and SQLite returns timezone columns without timezone metadata. Expired-attribute access can raise `MissingGreenlet`, while direct timestamp comparison raises `TypeError`.

**How to apply:** For worker persistence tests, use the worker's own session factory against the test database, keep primary-session IDs as plain strings, query committed rows explicitly after the worker finishes, and normalize SQLite-loaded timestamps before aware comparisons.