"""Input validation helpers."""

from __future__ import annotations

import re

SERVER_NAME_RE = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{1,61}[a-zA-Z0-9])?$")
SSH_KEY_NAME_RE = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")
SSH_PUBLIC_KEY_RE = re.compile(r"^(ssh-rsa|ssh-ed25519|ecdsa-sha2-nistp256|ecdsa-sha2-nistp384|ecdsa-sha2-nistp521)\s+")


def validate_server_name(name: str) -> str | None:
    """Validate a Hetzner server name. Returns an error message or None."""
    cleaned = name.strip()
    if len(cleaned) < 3 or len(cleaned) > 63:
        return "Please use 3-63 alphanumeric characters."
    if not SERVER_NAME_RE.match(cleaned):
        return "Please use 3-63 alphanumeric characters and hyphens only."
    return None


def validate_ssh_key_name(name: str) -> str | None:
    """Validate an SSH key name. Returns an error message or None."""
    cleaned = name.strip()
    if not cleaned or not SSH_KEY_NAME_RE.match(cleaned):
        return "Please use 1-64 characters: letters, numbers, dots, underscores, or hyphens."
    return None


def validate_root_password(password: str) -> str | None:
    """Validate a root password. Returns an error message or None."""
    cleaned = password.strip()
    if len(cleaned) < 8:
        return "Password must be at least 8 characters."
    if len(cleaned) > 128:
        return "Password must be at most 128 characters."
    if "\n" in cleaned or "\r" in cleaned:
        return "Password cannot contain line breaks."
    return None


def validate_ssh_public_key(public_key: str) -> str | None:
    """Validate an SSH public key. Returns an error message or None."""
    cleaned = public_key.strip()
    if not cleaned:
        return "Please send a valid SSH public key."
    if not SSH_PUBLIC_KEY_RE.match(cleaned):
        return "Unsupported key type. Use RSA, Ed25519, or ECDSA."
    parts = cleaned.split()
    if len(parts) < 2:
        return "Please send a valid SSH public key."
    return None
