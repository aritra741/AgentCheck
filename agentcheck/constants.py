"""Shared constants for AgentCheck runtime behavior."""

from __future__ import annotations

# Controlled timeout payload returned to agents for A1 scenarios.
TIMEOUT_RESPONSE: dict[str, str | int] = {
    "error": "timeout",
    "code": 408,
    "message": "Tool did not respond within the deadline.",
}

# Upper bound on optional real wall-clock sleep inside A1 injectors (milliseconds).
A1_REAL_SLEEP_CAP_MS = 100
