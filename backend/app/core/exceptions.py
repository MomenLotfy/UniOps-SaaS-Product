from fastapi import HTTPException, status


class UniOpsException(HTTPException):
    """
    Domain exception base — subclasses Starlette's HTTPException so that
    auth/RBAC/not-found failures (401/403/404) always produce a proper JSON
    error response in ANY FastAPI app that mounts our routers (including the
    bare per-module test apps), not an HTTP-500 unwind.

    The main app additionally registers a dedicated ``UniOpsException``
    handler (see main.py) preserving the historical
    ``{"success": False, "message", "code"}`` response contract.
    """

    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500,
                 headers: dict | None = None):
        super().__init__(
            status_code=status_code,
            detail={"message": message, "code": code, "status_code": status_code},
            headers=headers,
        )
        # Backward-compatible attribute surface used across the codebase
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundError(UniOpsException):
    def __init__(self, resource: str, resource_id: str = ""):
        super().__init__(
            message=f"{resource} not found" + (f": {resource_id}" if resource_id else ""),
            code="NOT_FOUND",
            status_code=404,
        )


class ProviderResourceNotFoundError(NotFoundError):
    """
    A 404 reported by the provider itself, carrying the provider's verbatim
    message.

    ``NotFoundError.__init__(resource, resource_id="")`` is designed for a
    *resource name* and formats ``f"{resource} not found"``. Passing an
    arbitrary provider message through it mangles the text — e.g. the provider
    error ``"deployment not found"`` became ``"deployment not found not found"``.

    This subclass keeps the 404 status and the ``NOT_FOUND`` code, and remains
    catchable as ``NotFoundError`` so existing ``except NotFoundError`` handlers
    (e.g. the re-raise in ``pods.cluster_summary``) keep working, while
    preserving the provider's wording.
    """

    def __init__(self, message: str):
        UniOpsException.__init__(
            self, message=message, code="NOT_FOUND", status_code=404
        )


class UnauthorizedError(UniOpsException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message=message, code="UNAUTHORIZED", status_code=401)


class ForbiddenError(UniOpsException):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message=message, code="FORBIDDEN", status_code=403)


class ValidationError(UniOpsException):
    def __init__(self, message: str, field: str = ""):
        super().__init__(message=message, code="VALIDATION_ERROR", status_code=422)
        self.field = field


class ConflictError(UniOpsException):
    def __init__(self, message: str):
        super().__init__(message=message, code="CONFLICT", status_code=409)


class IntegrationError(UniOpsException):
    def __init__(self, integration: str, message: str):
        super().__init__(
            message=f"{integration} integration error: {message}",
            code="INTEGRATION_ERROR",
            status_code=502,
        )


class IntegrationUnavailableError(UniOpsException):
    """Required integration is not connected/configured for this tenant."""

    def __init__(self, integration: str, message: str = "not connected"):
        super().__init__(
            message=f"{integration} integration unavailable: {message}",
            code="INTEGRATION_UNAVAILABLE",
            status_code=503,
        )


# ─────────────────────────────────────────────────────────────────────
#  Sprint 2 R19: domain-specific exceptions
#
#  These replace ad-hoc ``raise ValueError(...)`` calls across the
#  decision / strategy / approval / execution modules with typed
#  errors that carry a stable ``code`` and an HTTP ``status_code``
#  so the API layer can translate them deterministically.
# ─────────────────────────────────────────────────────────────────────
class DomainError(UniOpsException):
    """Base for all domain rule violations (state, lifecycle, invariant)."""

    def __init__(self, message: str, code: str, status_code: int = 422):
        super().__init__(message=message, code=code, status_code=status_code)


# Decision Engine ────────────────────────────────────────────────────
class DecisionNotFoundError(NotFoundError):
    def __init__(self, decision_id: str = ""):
        super().__init__("Decision", decision_id)


class DecisionInvariantError(DomainError):
    """Raised when an invariant required to create/produce a Decision is violated."""

    def __init__(self, message: str):
        super().__init__(message=message, code="DECISION_INVARIANT_VIOLATION", status_code=422)


class InvalidStateTransitionError(DomainError):
    """Raised when a Decision/Strategy/Approval/Execution state transition is illegal."""

    def __init__(self, from_state: str, to_state: str, entity: str = "Decision"):
        super().__init__(
            message=f"Illegal {entity} state transition: {from_state or 'NULL'} → {to_state}",
            code="INVALID_STATE_TRANSITION",
            status_code=409,
        )
        self.from_state = from_state
        self.to_state = to_state
        self.entity = entity


# Decision Strategy ──────────────────────────────────────────────────
class StrategyNotFoundError(NotFoundError):
    def __init__(self, strategy_id: str = ""):
        super().__init__("Strategy", strategy_id)


class InvalidStrategyTransitionError(InvalidStateTransitionError):
    def __init__(self, from_state: str, to_state: str):
        super().__init__(from_state=from_state, to_state=to_state, entity="Strategy")


class StrategyInvariantError(DomainError):
    def __init__(self, message: str):
        super().__init__(message=message, code="STRATEGY_INVARIANT_VIOLATION", status_code=422)


# Decision Approval ──────────────────────────────────────────────────
class ApprovalNotFoundError(NotFoundError):
    def __init__(self, approval_id: str = ""):
        super().__init__("Approval", approval_id)


class InvalidApprovalTransitionError(InvalidStateTransitionError):
    def __init__(self, from_state: str, to_state: str):
        super().__init__(from_state=from_state, to_state=to_state, entity="Approval")


class ApprovalInvariantError(DomainError):
    def __init__(self, message: str):
        super().__init__(message=message, code="APPROVAL_INVARIANT_VIOLATION", status_code=422)


class IdempotencyConflictError(ConflictError):
    """Raised when an Idempotency-Key has already been used with a different payload."""

    def __init__(self, idempotency_key: str):
        super().__init__(
            message=f"Idempotency-Key '{idempotency_key}' was previously used with a different payload"
        )
        self.idempotency_key = idempotency_key


# Execution Orchestration ────────────────────────────────────────────
class ExecutionNotFoundError(NotFoundError):
    def __init__(self, package_id: str = ""):
        super().__init__("ExecutionPackage", package_id)


class IllegalExecutionTransitionError(InvalidStateTransitionError):
    def __init__(self, from_state: str, to_state: str):
        super().__init__(from_state=from_state, to_state=to_state, entity="ExecutionPackage")


class MissingUpstreamError(DomainError):
    """Raised when an upstream entity (Decision/Strategy/Approval) is missing."""

    def __init__(self, upstream: str, reference: str = ""):
        super().__init__(
            message=f"Missing upstream {upstream}" + (f": {reference}" if reference else ""),
            code="MISSING_UPSTREAM",
            status_code=422,
        )
        self.upstream = upstream
        self.reference = reference


class ExecutionReadinessFailedError(DomainError):
    """Raised when the readiness stage produces one or more FAILED verdicts."""

    def __init__(self, factor: str, rationale: str, failed_count: int):
        super().__init__(
            message=f"Readiness failed: factor={factor} ({failed_count} failed) — {rationale}",
            code="READINESS_FAILED",
            status_code=409,
        )
        self.factor = factor
        self.rationale = rationale
        self.failed_count = failed_count
