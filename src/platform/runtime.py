"""Deployment profile and writable state directories."""

import os
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def is_serverless() -> bool:
    """True inside a Vercel Function (platform sets VERCEL) or when a local run
    opts in with FOOTBALL_SERVERLESS=1 to exercise the same code path."""
    return bool(os.environ.get("VERCEL")) or os.environ.get("FOOTBALL_SERVERLESS", "").strip() == "1"


def _resolve_state_root() -> Path:
    override = os.environ.get("FOOTBALL_STATE_DIR", "").strip()
    if override:
        return Path(override)
    if is_serverless():
        # Only the platform temp directory is writable inside a Function.
        return Path(tempfile.gettempdir()) / "football-rag"
    return PROJECT_ROOT


STATE_ROOT = _resolve_state_root()
OUTPUTS_DIR = STATE_ROOT / "outputs"
REPORTS_DIR = STATE_ROOT / "reports"
DATA_DIR = STATE_ROOT / "data"
GENERATED_PERSONAS_DIR = STATE_ROOT / "personas" / "generated"
