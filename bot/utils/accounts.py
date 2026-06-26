"""Persistent storage for multiple Hetzner API accounts."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from hcloud import Client

from bot.config import ACCOUNTS_FILE, HETZNER_TOKEN

logger = logging.getLogger(__name__)

_lock = threading.Lock()


@dataclass
class Account:
    """A named Hetzner Cloud API account."""

    id: str
    name: str
    token: str

    def masked_token(self) -> str:
        """Return a partially hidden token for display."""
        if len(self.token) <= 8:
            return "****"
        return f"{self.token[:4]}...{self.token[-4:]}"


def _read_raw() -> list[dict[str, str]]:
    if not ACCOUNTS_FILE.exists():
        return []
    try:
        data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read accounts file: %s", exc)
        return []


def _write_raw(accounts: list[Account]) -> None:
    ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(account) for account in accounts]
    ACCOUNTS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _bootstrap_from_env() -> None:
    """Seed accounts file from legacy HETZNER_TOKEN env variable."""
    if _read_raw() or not HETZNER_TOKEN:
        return
    _write_raw([Account(id=secrets.token_hex(4), name="Default", token=HETZNER_TOKEN)])


def load_accounts() -> list[Account]:
    """Load all configured accounts."""
    with _lock:
        _bootstrap_from_env()
        return [Account(**item) for item in _read_raw()]


def get_account(account_id: str) -> Account | None:
    """Find an account by ID."""
    return next((account for account in load_accounts() if account.id == account_id), None)


def add_account(*, name: str, token: str) -> Account:
    """Add a new account."""
    account = Account(id=secrets.token_hex(4), name=name.strip(), token=token.strip())
    with _lock:
        accounts = [Account(**item) for item in _read_raw()]
        if any(existing.name.lower() == account.name.lower() for existing in accounts):
            raise ValueError("An account with this name already exists.")
        accounts.append(account)
        _write_raw(accounts)
    return account


def remove_account(account_id: str) -> Account | None:
    """Remove an account by ID."""
    with _lock:
        accounts = [Account(**item) for item in _read_raw()]
        kept: list[Account] = []
        removed: Account | None = None
        for account in accounts:
            if account.id == account_id:
                removed = account
            else:
                kept.append(account)
        if removed:
            _write_raw(kept)
        return removed


def validate_token(token: str) -> None:
    """Verify that a Hetzner API token is valid."""
    client = Client(token=token.strip())
    client.servers.get_all()


async def validate_token_async(token: str) -> None:
    """Verify token without blocking the event loop."""
    await asyncio.to_thread(validate_token, token)
