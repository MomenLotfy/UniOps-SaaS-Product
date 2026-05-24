from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, model_validator


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
    # Result: every PATCH with {token: "ghp_..."} silently stored nothing,
    # the integration kept its old (empty) credentials, test_connection() got
    # an empty token, GitHub returned 401, status was set to "error" not
    # "connected", and every subsequent repo-sync query found zero rows.
    #
    # Fix: promote token → credentials.token before the dict leaves the schema
    # so IntegrationService.update() sees it in update_data["credentials"] and
    # correctly encrypts + merges it.
    # ─────────────────────────────────────────────────────────────────────────
    @model_validator(mode="after")
    def _promote_token_to_credentials(self) -> "IntegrationUpdate":
        if self.token:
            self.credentials = {**(self.credentials or {}), "token": self.token}
            self.token = None   # don't double-write into the DB column
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


class IntegrationTestResult(BaseModel):
    success: bool
    message: str
    details: Optional[Any] = None


class IntegrationSyncResult(BaseModel):
    integration_id: str
    synced_at: datetime
    records_synced: int = 0
    errors: list[str] = []
