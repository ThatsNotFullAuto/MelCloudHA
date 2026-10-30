"""Bounded operational telemetry with no account, device ID, payload or credential fields."""

from collections import Counter, deque
from datetime import UTC, datetime


class DiagnosticHealth:
    def __init__(self):
        self.started_at = datetime.now(UTC).isoformat()
        self.events = deque(maxlen=100)
        self.counts = Counter()
        self.http_statuses = {}

    def record(self, operation, status, duration_ms, error_type=None):
        self.counts[f"{operation}:{status}"] += 1
        event = {
            "at": datetime.now(UTC).isoformat(),
            "operation": operation,
            "status": status,
            "duration_ms": round(duration_ms, 1),
        }
        if error_type:
            event["error_type"] = error_type
        self.events.append(event)

    def export(self):
        return {
            "started_at": self.started_at,
            "counters": dict(self.counts),
            "last_http_status": dict(self.http_statuses),
            "recent_requests": list(self.events),
        }
