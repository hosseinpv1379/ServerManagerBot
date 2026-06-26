"""Format Hetzner resources for Telegram messages."""

from __future__ import annotations

from datetime import datetime, timezone

from hcloud.images.domain import Image
from hcloud.locations.domain import Location
from hcloud.servers.domain import Server
from hcloud.ssh_keys.domain import SSHKey


def _days_ago(value: datetime | None) -> str:
    if not value:
        return "unknown"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    days = (datetime.now(tz=timezone.utc) - value).days
    return f"{days} day{'s' if days != 1 else ''} ago"


def _format_gb(value: int | float | None) -> str:
    if value is None:
        return "—"
    return f"{value:g} GB"


def format_server(server: Server) -> str:
    """Format detailed server information."""
    ipv4 = server.public_net.ipv4.ip if server.public_net.ipv4 else "—"
    ipv6 = server.public_net.ipv6.ip if server.public_net.ipv6 else "—"
    location = server.datacenter.location
    image_name = server.image.name or server.image.description or "—"

    incoming_gb = round((server.ingoing_traffic or 0) / 1024**3, 2)
    outgoing_gb = round((server.outgoing_traffic or 0) / 1024**3, 2)
    included_gb = round((getattr(server, "included_traffic", 0) or 0) / 1024**3, 2)

    return (
        f"<b>Server:</b> <code>{server.name}</code>\n"
        f"<b>Status:</b> <code>{server.status}</code>\n"
        f"<b>IPv4:</b> <code>{ipv4}</code>\n"
        f"<b>IPv6:</b> <code>{ipv6}</code>\n"
        f"<b>Location:</b> <code>{location.city}, {location.country}</code>\n"
        f"<b>CPU:</b> <code>{server.server_type.cores} cores</code>\n"
        f"<b>RAM:</b> <code>{_format_gb(server.server_type.memory)}</code>\n"
        f"<b>Disk:</b> <code>{_format_gb(server.server_type.disk)}</code>\n"
        f"<b>Image:</b> <code>{image_name}</code>\n"
        f"<b>Traffic out:</b> <code>{outgoing_gb} GB</code> / "
        f"<code>{included_gb} GB</code> included\n"
        f"<b>Traffic in:</b> <code>{incoming_gb} GB</code>\n"
        f"<b>Created:</b> <code>{server.created.strftime('%Y-%m-%d %H:%M UTC')}</code> "
        f"[{_days_ago(server.created)}]"
    )


def format_server_summary(server: Server) -> str:
    """Format a one-line server summary for list views."""
    ipv4 = server.public_net.ipv4.ip if server.public_net.ipv4 else "no IPv4"
    return f"<code>{server.name}</code> — {server.status} — {ipv4}"


def format_server_list(servers: list[Server], *, page: int, page_size: int) -> str:
    """Format a paginated server list header."""
    if not servers:
        return "<b>Servers</b>\n\nNo servers found."
    start = page * page_size
    end = min(start + page_size, len(servers))
    lines = [f"<b>Servers</b> ({start + 1}-{end} of {len(servers)})\n"]
    for server in servers[start:end]:
        lines.append(f"• {format_server_summary(server)}")
    return "\n".join(lines)


def format_image(image: Image) -> str:
    """Format detailed image information."""
    return (
        f"<b>Image:</b> <code>{image.name or image.description}</code>\n"
        f"<b>Type:</b> <code>{image.type}</code>\n"
        f"<b>OS:</b> <code>{image.os_flavor or '—'}</code> "
        f"<code>{image.os_version or ''}</code>\n"
        f"<b>Architecture:</b> <code>{image.architecture or '—'}</code>\n"
        f"<b>Status:</b> <code>{image.status or '—'}</code>\n"
        f"<b>Disk size:</b> <code>{_format_gb(image.disk_size)}</code>\n"
        f"<b>Created:</b> <code>{image.created.strftime('%Y-%m-%d %H:%M UTC') if image.created else '—'}</code>"
    )


def format_image_list(images: list[Image], *, page: int, page_size: int) -> str:
    """Format a paginated image list header."""
    if not images:
        return "<b>Images</b>\n\nNo images found."
    start = page * page_size
    end = min(start + page_size, len(images))
    lines = [f"<b>Images</b> ({start + 1}-{end} of {len(images)})\n"]
    for image in images[start:end]:
        label = image.name or image.description or str(image.id)
        lines.append(f"• <code>{label}</code> [{image.os_flavor or image.type}]")
    return "\n".join(lines)


def format_location(location: Location) -> str:
    """Format detailed location information."""
    return (
        f"<b>Location:</b> <code>{location.name}</code>\n"
        f"<b>City:</b> <code>{location.city}</code>\n"
        f"<b>Country:</b> <code>{location.country}</code>\n"
        f"<b>Description:</b> {location.description}\n"
        f"<b>Network zone:</b> <code>{location.network_zone}</code>"
    )


def format_location_list(locations: list[Location]) -> str:
    """Format a location list."""
    if not locations:
        return "<b>Locations</b>\n\nNo locations found."
    lines = ["<b>Locations</b>\n"]
    for location in locations:
        lines.append(f"• <code>{location.name}</code> — {location.city}, {location.country}")
    return "\n".join(lines)


def format_ssh_key(ssh_key: SSHKey) -> str:
    """Format detailed SSH key information."""
    fingerprint = ssh_key.fingerprint or "—"
    return (
        f"<b>Name:</b> <code>{ssh_key.name}</code>\n"
        f"<b>Fingerprint:</b> <code>{fingerprint}</code>\n"
        f"<b>Created:</b> <code>{ssh_key.created.strftime('%Y-%m-%d %H:%M UTC') if ssh_key.created else '—'}</code>"
    )


def format_ssh_key_list(keys: list[SSHKey]) -> str:
    """Format an SSH key list."""
    if not keys:
        return "<b>SSH Keys</b>\n\nNo SSH keys found."
    lines = ["<b>SSH Keys</b>\n"]
    for key in keys:
        lines.append(f"• <code>{key.name}</code>")
    return "\n".join(lines)
