"""DevOps Center regression suite.

Covers the defects documented in DEVOPS_CENTER_PRODUCTION_AUDIT.md:
  BUG-001  GitHub mutation headers
  BUG-002  Kubernetes V1DeleteOptions
  BUG-003  reconciliation safety after provider failure
  BUG-004  pod exec false success
  BUG-006  deployment scale false success
  plus cluster routing, tenant isolation and the provider-failure contract.
"""
