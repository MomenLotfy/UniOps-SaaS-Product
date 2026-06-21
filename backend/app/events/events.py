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

    # ── Epic 9 — Real Control Plane events ───────────────────────────────────
    POD_CREATED   = "pod.created"
    POD_UPDATED   = "pod.updated"
    POD_FAILED    = "pod.failed"
    POD_RESTARTED = "pod.restarted"
    POD_DELETED   = "pod.deleted"

    PIPELINE_RUNNING = "pipeline.running"

    SERVICE_DEPLOYING = "service.deploying"
    SERVICE_DEPLOYED  = "service.deployed"
    SERVICE_FAILED    = "service.failed"

    METRIC_UPDATED = "metric.updated"
    LOG_STREAM     = "log.stream"

    GITOPS_SYNCED    = "gitops.synced"
    GITOPS_OUT_OF_SYNC = "gitops.out_of_sync"
    GITOPS_DEGRADED  = "gitops.degraded"

    CLUSTER_CONNECTED    = "cluster.connected"
    CLUSTER_DISCONNECTED = "cluster.disconnected"
    CLUSTER_ERROR        = "cluster.error"
