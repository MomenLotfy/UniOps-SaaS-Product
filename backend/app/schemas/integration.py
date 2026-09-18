from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, model_validator, computed_field


# Types with a REAL provider client (IntegrationService._build_client).
# Any other name used to silently fall through to a fake "always succeeds"
# stub (BUG-P2-03) — unknown types are now rejected at the boundary with 422.
SUPPORTED_INTEGRATION_TYPES = frozenset({
    "github", "gitlab", "aws", "kubernetes", "stripe",
})


class IntegrationCreate(BaseModel):
    name: str
    type: str
    credentials: dict = {}
    config: dict = {}
    token: Optional[str] = None    # convenience alias — promoted into credentials.token

    @model_validator(mode="after")
    def _promote_token_to_credentials(self) -> "IntegrationCreate":
        if self.token:
            self.credentials = {**self.credentials, "token": self.token}
            self.token = None
        # BUG-P2-03: unknown types must never reach the service layer pretending
        # to be a real provider — reject them here so the API answers 422.
        if self.type.lower() not in SUPPORTED_INTEGRATION_TYPES:
            raise ValueError(
                f"unsupported integration type '{self.type}' — supported: "
                + ", ".join(sorted(SUPPORTED_INTEGRATION_TYPES))
            )
        self.type = self.type.lower()
        return self


class IntegrationUpdate(BaseModel):
    name: Optional[str] = None
    credentials: Optional[dict] = None
    config: Optional[dict] = None
    is_active: Optional[bool] = None
    status: Optional[str] = None   # allow frontend to set connected/disconnected
    token: Optional[str] = None    # convenience alias — promoted into credentials.token

    # ── FIX #1 ────────────────────────────────────────────────────────────────
    # The `token` convenience field was declared but NEVER moved into credentials
    # by the schema or the service. The service's update() only processes
    # update_data["credentials"] — it never read update_data["token"] at all.
    # ─────────────────────────────────────────────────────────────────────────
    @model_validator(mode="after")
    def _promote_token_to_credentials(self) -> "IntegrationUpdate":
        if self.token:
            self.credentials = {**(self.credentials or {}), "token": self.token}
            self.token = None
        return self


class IntegrationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    name: str
    type: str
    status: str
    is_active: bool
    last_sync: Optional[datetime] = None
    error_message: Optional[str] = None
    config: dict = {}
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def provider(self) -> str:
        """Frontend expects 'provider' field, but DB uses 'type'."""
        return self.type


class IntegrationTestResult(BaseModel):
    success: bool
    message: str
    details: Optional[Any] = None


class IntegrationSyncResult(BaseModel):
    integration_id: str
    synced_at: datetime
    records_synced: int = 0
    errors: list[str] = []
