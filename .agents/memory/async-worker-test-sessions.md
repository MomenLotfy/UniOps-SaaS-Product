---
name: Async worker test sessions
description: Safe verification pattern for background workers that commit through a separate SQLAlchemy async session.
---

When an async worker is tested with a separate database session, capture identifiers before the worker runs and use fresh queries with explicit refresh/populate behavior afterward. Do not expire objects in the original `AsyncSession` and then access their attributes.

**Why:** The original test session may hold stale identity-map state, and an expired attribute reload outside SQLAlchemy's async greenlet raises `MissingGreenlet` instead of returning the committed value.

**How to apply:** For worker persistence tests, use the worker's own session factory against the test database, keep primary-session IDs as plain strings, and query committed rows explicitly after the worker finishes.