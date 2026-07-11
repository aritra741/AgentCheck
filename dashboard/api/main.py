"""FastAPI application entry point for AgentCheck dashboard."""

from __future__ import annotations

import shutil
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from dashboard.api.demo_mcp import router as demo_mcp_router
from dashboard.api.workbench import router

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
SEED_DB = REPO_ROOT / "dashboard" / "seed" / "agentcheck.db"
TARGET_DB = REPO_ROOT / "agentcheck.db"
load_dotenv()


def _ensure_bundled_db() -> None:
    """Copy the seed DB into place when missing or empty (no comparisons)."""
    if not SEED_DB.exists():
        return
    if TARGET_DB.exists():
        try:
            import sqlite3

            with sqlite3.connect(TARGET_DB) as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='comparisons'"
                ).fetchone()
                if row and row[0]:
                    count = conn.execute("SELECT COUNT(*) FROM comparisons").fetchone()[0]
                    if count:
                        return
        except Exception:
            pass
    shutil.copy(SEED_DB, TARGET_DB)


_ensure_bundled_db()

app = FastAPI(title="AgentCheck Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(demo_mcp_router)
app.include_router(router)

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
