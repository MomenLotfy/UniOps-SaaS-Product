from prometheus_client import Counter, Histogram, Gauge

http_requests_total = Counter(
    "uniops_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration = Histogram(
    "uniops_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
)

active_users = Gauge("uniops_active_users", "Number of active users")
active_websockets = Gauge("uniops_active_websockets", "Active WebSocket connections")
