from __future__ import annotations
from pydantic_settings import BaseSettings
from typing import Dict, Any

class RemediationSettings(BaseSettings):
    """
    Central configuration for the Remediation Engine.
    Values are loaded from environment variables or defaults.
    """
    # ── General ──────────────────────────────────────────────────────────────────
    # Provider for the event bus: 'internal', 'redis', 'kafka', etc.
    event_bus_provider: str = "internal"
    # Provider for locking: 'memory', 'redis', 'zookeeper'
    lock_provider: str = "memory"

    # ── Execution Limits ──────────────────────────────────────────────────────────
    # Maximum number of concurrent executions per tenant
    max_concurrent_executions_per_tenant: int = 5
    # Maximum number of concurrent executions globally
    max_global_executions: int = 100
    # Default timeout for a single execution stage (seconds)
    default_stage_timeout_seconds: int = 300
    # Maximum total execution time for a plan (seconds)
    max_execution_timeout_seconds: int = 3600

    # ── Retry Policy ─────────────────────────────────────────────────────────────
    # Default max attempts for a failed stage
    max_retry_attempts: int = 3
    # Exponential backoff multiplier
    retry_backoff_multiplier: float = 2.0
    # Initial retry delay (seconds)
    retry_initial_delay_seconds: int = 5

    # ── Feature Flags ────────────────────────────────────────────────────────────
    # Enable/Disable AI-assisted planning
    enable_ai_decision_support: bool = True
    # Enable/Disable auto-remediation for low-risk findings
    enable_auto_remediation: bool = False
    # Enable/Disable distributed tracing (OpenTelemetry)
    enable_distributed_tracing: bool = False

    # ── Versioning ───────────────────────────────────────────────────────────────
    engine_version: str = "1.0.0"

    class Config:
        env_prefix = "REMEDIATION_"

# Global settings instance
remediation_settings = RemediationSettings()
