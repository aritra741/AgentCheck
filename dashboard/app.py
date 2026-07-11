"""Local server entry point for the AgentCheck dashboard."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "dashboard.api.main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
    )
