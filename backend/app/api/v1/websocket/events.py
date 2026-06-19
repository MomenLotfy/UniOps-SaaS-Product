"""WebSocket event type definitions."""
from enum import Enum


class WSEventType(str, Enum):
    # Ping/Pong
    PING = "ping"
    PONG = "pong"

    # Alerts
    ALERT_NEW = "alert.new"
    ALERT_RESOLVED = "alert.resolved"
    ALERT_STATS_UPDATE = "alert.stats_update"

    # Pipelines
    PIPELINE_UPDATE = "pipeline.update"
    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_FAILED = "pipeline.failed"

    # Pods / Kubernetes
    POD_UPDATE = "pod.update"
    POD_FAILED = "pod.failed"
    POD_RESTARTED = "pod.restarted"

    # Security
    THREAT_DETECTED = "threat.detected"
    VULNERABILITY_FOUND = "vulnerability.found"
    COMPLIANCE_UPDATED = "compliance.updated"

    # Scan lifecycle
    SCAN_STARTED   = "scan.started"
    SCAN_COMPLETED = "scan.completed"
    SCAN_FAILED    = "scan.failed"
    SCAN_PROGRESS  = "scan.progress"

    # Costs
    COST_ANOMALY = "cost.anomaly"
    COST_THRESHOLD_EXCEEDED = "cost.threshold_exceeded"

    # ML
    ML_INSIGHT = "ml.insight"
    ML_RECOMMENDATION = "ml.recommendation"
    ML_MODEL_TRAINED = "ml.model_trained"

    # Integrations
    INTEGRATION_CONNECTED = "integration.connected"
    INTEGRATION_DISCONNECTED = "integration.disconnected"
    INTEGRATION_SYNC_DONE = "integration.sync_done"

    # System
    NOTIFICATION = "notification"
    SYSTEM_MESSAGE = "system.message"
    USER_ACTIVITY = "user.activity"
