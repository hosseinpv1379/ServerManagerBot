"""Configuration and constants for the Hetzner Cloud Telegram bot."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
HETZNER_TOKEN: str = os.getenv("HETZNER_TOKEN", "")


def _parse_admin_ids(raw: str) -> list[int]:
    """Parse comma-separated Telegram user IDs."""
    ids: list[int] = []
    for part in raw.split(","):
        cleaned = part.strip()
        if cleaned.isdigit():
            ids.append(int(cleaned))
    return ids


_admin_ids_raw = os.getenv("ADMIN_USER_IDS", "") or os.getenv("ADMIN_USER_ID", "")
ADMIN_USER_IDS: list[int] = _parse_admin_ids(_admin_ids_raw)

BASE_DIR = Path(__file__).resolve().parent.parent
ACCOUNTS_FILE = BASE_DIR / "data" / "accounts.json"

PAGE_SIZE: int = 5
CACHE_TTL_SECONDS: int = 8

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
