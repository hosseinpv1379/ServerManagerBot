"""Orchestrate Hetzner API reset + SSH server configuration."""

from __future__ import annotations

import asyncio
import logging

from hcloud.servers.domain import Server

from bot.utils.api import HetznerAPI
from bot.utils.ssh_client import SSHError, add_public_key, get_server_host, set_root_password

logger = logging.getLogger(__name__)

STARTUP_WAIT_SECONDS = 8
RUNNING_POLL_ATTEMPTS = 24
RUNNING_POLL_DELAY = 5


async def ensure_server_running(api: HetznerAPI, server: Server) -> Server:
    """Power on the server if needed and wait until it is running."""
    if server.status != "running":
        if server.status == "off":
            await api.power_on_server(server)
        for _ in range(RUNNING_POLL_ATTEMPTS):
            await asyncio.sleep(RUNNING_POLL_DELAY)
            server = await api.get_server(server.id)
            if server and server.status == "running":
                break
        else:
            raise SSHError("Server did not reach running state in time.")

    await asyncio.sleep(STARTUP_WAIT_SECONDS)
    refreshed = await api.get_server(server.id)
    if not refreshed:
        raise SSHError("Server not found after startup.")
    return refreshed


async def set_custom_root_password(
    api: HetznerAPI,
    server: Server,
    new_password: str,
) -> Server:
    """Reset via Hetzner, SSH in, and set a custom root password."""
    server = await ensure_server_running(api, server)
    host = get_server_host(server)

    temp_password = await api.reset_server_password(server)
    await asyncio.sleep(STARTUP_WAIT_SECONDS)

    await asyncio.to_thread(set_root_password, host, temp_password, new_password)
    logger.info("Custom root password set on server %s (%s)", server.name, host)

    refreshed = await api.get_server(server.id)
    if not refreshed:
        raise SSHError("Server not found after password change.")
    return refreshed


async def install_public_key_on_server(
    api: HetznerAPI,
    server: Server,
    public_key: str,
) -> tuple[Server, str, bool]:
    """Reset via Hetzner, SSH in, and install a public key on the server."""
    server = await ensure_server_running(api, server)
    host = get_server_host(server)

    temp_password = await api.reset_server_password(server)
    await asyncio.sleep(STARTUP_WAIT_SECONDS)

    added = await asyncio.to_thread(add_public_key, host, temp_password, public_key)
    logger.info("SSH key %s on server %s (%s)", "added to" if added else "already on", server.name, host)

    refreshed = await api.get_server(server.id)
    if not refreshed:
        raise SSHError("Server not found after SSH key installation.")
    return refreshed, temp_password, added
