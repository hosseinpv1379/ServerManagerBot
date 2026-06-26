"""Register all Telegram bot handlers."""

from __future__ import annotations

from telegram.ext import Application

from bot.handlers.account import register_account_handlers
from bot.handlers.general import register_general_handlers
from bot.handlers.image import register_image_handlers
from bot.handlers.location import register_location_handlers
from bot.handlers.middleware import register_access_middleware
from bot.handlers.server import register_server_handlers
from bot.handlers.ssh_key import register_ssh_key_handlers


def setup_handlers(application: Application) -> None:
    """Attach all feature handlers to the application."""
    register_access_middleware(application)
    register_account_handlers(application)
    register_server_handlers(application)
    register_ssh_key_handlers(application)
    register_image_handlers(application)
    register_location_handlers(application)
    register_general_handlers(application)
