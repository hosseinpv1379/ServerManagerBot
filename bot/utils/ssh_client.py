"""SSH operations on Hetzner servers via paramiko."""

from __future__ import annotations

import logging
import time

import paramiko
from hcloud.servers.domain import Server

logger = logging.getLogger(__name__)

SSH_PORT = 22
SSH_CONNECT_TIMEOUT = 30
SSH_RETRY_ATTEMPTS = 12
SSH_RETRY_DELAY = 5


class SSHError(Exception):
    """Raised when SSH command execution fails."""


def get_server_host(server: Server) -> str:
    """Return the server's public IP address."""
    if server.public_net.ipv4 and server.public_net.ipv4.ip:
        return server.public_net.ipv4.ip
    if server.public_net.ipv6 and server.public_net.ipv6.ip:
        return server.public_net.ipv6.ip
    raise SSHError("Server has no public IP address.")


def _connect(host: str, password: str) -> paramiko.SSHClient:
    """Open an SSH session to the server."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        port=SSH_PORT,
        username="root",
        password=password,
        timeout=SSH_CONNECT_TIMEOUT,
        look_for_keys=False,
        allow_agent=False,
        banner_timeout=SSH_CONNECT_TIMEOUT,
        auth_timeout=SSH_CONNECT_TIMEOUT,
    )
    return client


def _connect_with_retry(host: str, password: str) -> paramiko.SSHClient:
    """Retry SSH connection while the server applies the new password."""
    last_error: Exception | None = None
    for attempt in range(SSH_RETRY_ATTEMPTS):
        try:
            return _connect(host, password)
        except (paramiko.SSHException, OSError, TimeoutError) as exc:
            last_error = exc
            logger.info("SSH attempt %s/%s failed for %s: %s", attempt + 1, SSH_RETRY_ATTEMPTS, host, exc)
            time.sleep(SSH_RETRY_DELAY)
    raise SSHError(f"Could not connect via SSH after {SSH_RETRY_ATTEMPTS} attempts.") from last_error


def _run_command(client: paramiko.SSHClient, command: str) -> None:
    """Run a shell command and raise on non-zero exit."""
    _, stdout, stderr = client.exec_command(command, get_pty=False)
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        error = stderr.read().decode("utf-8", errors="replace").strip()
        raise SSHError(error or f"Command failed with exit code {exit_code}")


def set_root_password(host: str, current_password: str, new_password: str) -> None:
    """Connect via SSH and change the root password."""
    client = _connect_with_retry(host, current_password)
    try:
        stdin, stdout, stderr = client.exec_command("chpasswd", get_pty=False)
        stdin.write(f"root:{new_password}\n")
        stdin.flush()
        stdin.channel.shutdown_write()
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            error = stderr.read().decode("utf-8", errors="replace").strip()
            raise SSHError(error or "Failed to change root password.")
    finally:
        client.close()


def add_public_key(host: str, password: str, public_key: str) -> bool:
    """Append a public key to root authorized_keys. Returns True if added."""
    key = public_key.strip()
    client = _connect_with_retry(host, password)
    try:
        _run_command(client, "mkdir -p /root/.ssh && chmod 700 /root/.ssh")
        sftp = client.open_sftp()
        path = "/root/.ssh/authorized_keys"
        try:
            with sftp.open(path, "r") as handle:
                existing = handle.read().decode("utf-8", errors="replace")
        except OSError:
            existing = ""

        if key in existing:
            return False

        content = f"{existing.rstrip()}\n{key}\n" if existing.strip() else f"{key}\n"
        with sftp.open(path, "w") as handle:
            handle.write(content)
        sftp.close()
        _run_command(client, f"chmod 600 {path}")
        return True
    finally:
        client.close()
