from enum import Enum


class EventType(str, Enum):
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    INTEGRATION_CONNECTED = "integration.connected"
    INTEGRATION_DISCONNECTED = "integration.disconnected"
    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_FAILED = "pipeline.failed"
    THREAT_DETECTED = "threat.detected"
    VULNERABILITY_FOUND = "vulnerability.found"
    COST_ANOMALY_DETECTED = "cost.anomaly_detected"
    ALERT_FIRED = "alert.fired"
    ALERT_RESOLVED = "alert.resolved"
