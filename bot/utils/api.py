"""Async wrapper around the official Hetzner Cloud Python SDK."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from hcloud import Client
from hcloud._exceptions import APIException
from hcloud.images.domain import Image
from hcloud.locations.domain import Location
from hcloud.servers.domain import Server
from hcloud.ssh_keys.domain import SSHKey

from bot.config import CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)

T = TypeVar("T")


class HetznerAPIError(Exception):
    """User-friendly wrapper for Hetzner API failures."""

    def __init__(self, message: str, *, original: Exception | None = None) -> None:
        super().__init__(message)
        self.original = original


class HetznerAPI:
    """Thread-safe async facade over the synchronous hcloud client."""

    def __init__(self, token: str) -> None:
        self._client = Client(
            token=token,
            application_name="ServerManagerBot",
            application_version="1.0.0",
        )
        self._cache: dict[str, tuple[float, Any]] = {}

    async def _run(self, fn: Callable[[], T]) -> T:
        """Execute a blocking hcloud call in a worker thread."""
        try:
            return await asyncio.to_thread(fn)
        except APIException as exc:
            raise self._translate_error(exc) from exc
        except Exception as exc:
            logger.exception("Unexpected Hetzner API error")
            raise HetznerAPIError("Connection error, please try again.", original=exc) from exc

    async def _cached(self, key: str, fn: Callable[[], T]) -> T:
        """Return cached results for short-lived list operations."""
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]

        result = await self._run(fn)
        self._cache[key] = (now, result)
        return result

    def invalidate(self, *keys: str) -> None:
        """Drop cached entries after mutating operations."""
        for key in keys:
            self._cache.pop(key, None)

    @staticmethod
    def _translate_error(exc: APIException) -> HetznerAPIError:
        code = getattr(exc, "code", None)
        message = str(exc).lower()

        if code == "rate_limit_exceeded" or "rate limit" in message:
            return HetznerAPIError("Too many requests, please wait a moment and try again.", original=exc)
        if code == "resource_limit_exceeded" or "limit" in message:
            return HetznerAPIError("Account limit reached, cannot complete this action.", original=exc)
        if code == "invalid_input":
            return HetznerAPIError(f"Invalid input: {exc.message}", original=exc)
        return HetznerAPIError(f"API error: {exc.message}", original=exc)

    async def get_servers(self) -> list[Server]:
        """List all servers."""
        return await self._cached("servers", self._client.servers.get_all)

    async def get_server(self, server_id: int) -> Server | None:
        """Fetch a single server by ID."""
        return await self._run(lambda: self._client.servers.get_by_id(server_id))

    async def create_server(
        self,
        *,
        name: str,
        server_type_name: str,
        image_name: str,
        location_name: str,
        ssh_keys: list[SSHKey] | None = None,
    ) -> tuple[Server, str | None]:
        """Create a server and return it with an optional root password."""
        from hcloud.images import Image as ImageRef
        from hcloud.locations import Location as LocationRef
        from hcloud.server_types import ServerType

        def _create() -> tuple[Server, str | None]:
            response = self._client.servers.create(
                name=name,
                server_type=ServerType(name=server_type_name),
                image=ImageRef(name=image_name),
                location=LocationRef(name=location_name),
                ssh_keys=ssh_keys or [],
            )
            return response.server, response.root_password

        result = await self._run(_create)
        self.invalidate("servers")
        return result

    async def delete_server(self, server: Server) -> None:
        """Delete a server."""
        await self._run(lambda: self._client.servers.delete(server))
        self.invalidate("servers")

    async def reboot_server(self, server: Server) -> None:
        """Reboot a server."""
        await self._run(lambda: server.reboot())

    async def power_on_server(self, server: Server) -> None:
        """Power on a server."""
        await self._run(lambda: server.power_on())

    async def power_off_server(self, server: Server) -> None:
        """Power off a server."""
        await self._run(lambda: server.power_off())

    async def reset_server_password(self, server: Server) -> str:
        """Reset root password and return the new password."""
        def _reset() -> str:
            response = server.reset_password()
            return response.root_password

        return await self._run(_reset)

    async def get_images(self, *, os_filter: str | None = None) -> list[Image]:
        """List system images, optionally filtered by OS name."""
        images = await self._cached("images", lambda: self._client.images.get_all(type="system"))
        if os_filter:
            needle = os_filter.lower()
            images = [
                image
                for image in images
                if needle in (image.name or "").lower() or needle in (image.description or "").lower()
            ]
        return sorted(images, key=lambda image: (image.os_flavor or "", image.name or ""))

    async def get_image(self, image_id: int) -> Image | None:
        """Fetch a single image by ID."""
        return await self._run(lambda: self._client.images.get_by_id(image_id))

    async def get_locations(self) -> list[Location]:
        """List all locations."""
        return await self._cached("locations", self._client.locations.get_all)

    async def get_location(self, location_id: int) -> Location | None:
        """Fetch a single location by ID."""
        return await self._run(lambda: self._client.locations.get_by_id(location_id))

    async def get_server_types(self) -> list[Any]:
        """List available server types sorted by monthly price."""
        types = await self._cached("server_types", self._client.server_types.get_all)

        def _monthly_price(server_type: Any) -> float:
            prices = server_type.prices or []
            if not prices:
                return 0.0
            monthly = prices[0].get("price_monthly", {})
            return float(monthly.get("net", 0))

        return sorted(types, key=_monthly_price)

    async def get_ssh_keys(self) -> list[SSHKey]:
        """List all SSH keys."""
        return await self._cached("ssh_keys", self._client.ssh_keys.get_all)

    async def get_ssh_key(self, key_id: int) -> SSHKey | None:
        """Fetch a single SSH key by ID."""
        return await self._run(lambda: self._client.ssh_keys.get_by_id(key_id))

    async def create_ssh_key(self, *, name: str, public_key: str) -> SSHKey:
        """Create a new SSH key."""
        result = await self._run(lambda: self._client.ssh_keys.create(name=name, public_key=public_key))
        self.invalidate("ssh_keys")
        return result

    async def delete_ssh_key(self, ssh_key: SSHKey) -> None:
        """Delete an SSH key."""
        await self._run(lambda: self._client.ssh_keys.delete(ssh_key))
        self.invalidate("ssh_keys")


_api_cache: dict[str, HetznerAPI] = {}


def get_api(account_id: str) -> HetznerAPI:
    """Return a cached Hetzner API client for the given account."""
    from bot.utils.accounts import get_account

    if account_id not in _api_cache:
        account = get_account(account_id)
        if not account:
            raise HetznerAPIError("Selected API account was not found.")
        _api_cache[account_id] = HetznerAPI(account.token)
    return _api_cache[account_id]


def get_api_for_context(context) -> HetznerAPI:
    """Return the API client for the user's currently selected account."""
    account_id = context.user_data.get("account_id")
    if not account_id:
        raise HetznerAPIError("No API account selected. Use /start to choose one.")
    return get_api(account_id)


def clear_api_cache(account_id: str | None = None) -> None:
    """Drop cached API clients after account changes."""
    if account_id:
        _api_cache.pop(account_id, None)
    else:
        _api_cache.clear()
