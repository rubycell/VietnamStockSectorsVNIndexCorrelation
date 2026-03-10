"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'data' / 'portfolio.db'}")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

VNSTOCK_SOURCE = os.getenv("VNSTOCK_SOURCE", "VCI")
MARKET_OPEN_HOUR = int(os.getenv("MARKET_OPEN_HOUR", "9"))
MARKET_CLOSE_HOUR = int(os.getenv("MARKET_CLOSE_HOUR", "15"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")

DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DATA_DIR = PROJECT_ROOT / "data"
