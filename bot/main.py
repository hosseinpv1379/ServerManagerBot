"""Hetzner Cloud Telegram bot entry point."""

from __future__ import annotations

import logging

from telegram.ext import Application

from bot.config import ADMIN_USER_IDS, HETZNER_TOKEN, TELEGRAM_BOT_TOKEN, logger
from bot.handlers import setup_handlers

logger = logging.getLogger(__name__)


def validate_config() -> None:
    """Ensure required environment variables are set."""
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not ADMIN_USER_IDS:
        missing.append("ADMIN_USER_IDS")
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    if not HETZNER_TOKEN:
        logger.warning(
            "HETZNER_TOKEN is not set. Add API accounts via the bot or set HETZNER_TOKEN in .env."
        )


def build_application() -> Application:
    """Build and configure the Telegram application."""
    validate_config()
    logger.info("Admin user IDs: %s", ADMIN_USER_IDS)
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .build()
    )
    setup_handlers(application)
    return application


def main() -> None:
    """Start the bot."""
    logger.info("Starting Hetzner Cloud Telegram bot...")
    application = build_application()
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
