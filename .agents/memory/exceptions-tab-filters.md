---
name: Exceptions tab filters
description: Category filter field name mismatch, revoke IDOR prevention, severity JSON accessor pattern.
---

## Category filter field name

The Security Exceptions model stores the finding category in `finding_type` (not `exception_type`). The `exception_type` column stores the duration type (temporary/permanent).

- **Frontend** sends: `?category=<value>` (NOT `exception_type=<value>`)
- **Backend** maps: `category` query param → `SecurityException.finding_type` filter

**Why:** A pre-existing bug sent `exception_type=category_value` which filtered on the wrong column and returned wrong results. Fixed in `security_exceptions.py` endpoint and `security_exception_service.py`.

## Revoke IDOR prevention

`revoke_exception()` in the service must receive and enforce `tenant_id`. The base `_get_by_id()` only loads by primary key — it does NOT enforce tenant isolation.

Pattern for all mutating operations that don't go through `list_exceptions` (which already has `tenant_id` in WHERE):
```python
exc = await self._get_by_id(SecurityException, exception_id)
if exc.tenant_id != tenant_id:
    raise NotFoundError(...)  # don't leak existence
```

## Severity filter (JSON column)

`tags` is a JSON column (not JSONB). Use SQLAlchemy's JSON key accessor for deterministic extraction:
```python
cast(SecurityException.tags["severity"], Text) == f'"{severity}"'
```

Do NOT use `cast(tags, Text).ilike(...)` — JSON serialization order/whitespace is not guaranteed.
