from fastapi import HTTPException, status


class UniOpsException(Exception):
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(UniOpsException):
    def __init__(self, resource: str, resource_id: str = ""):
        super().__init__(
            message=f"{resource} not found" + (f": {resource_id}" if resource_id else ""),
            code="NOT_FOUND",
            status_code=404,
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
