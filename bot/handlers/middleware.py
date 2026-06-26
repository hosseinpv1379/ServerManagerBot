"""Access control middleware."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, ApplicationHandlerStop, ContextTypes, TypeHandler

from bot.config import ADMIN_USER_IDS
from bot.handlers.common import is_admin

logger = logging.getLogger(__name__)


async def admin_only_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Block all updates from non-admin users."""
    user = update.effective_user
    if user and is_admin(user.id):
        return

    user_label = user.id if user else "unknown"
    logger.warning("Blocked non-admin access from user %s", user_label)

    if update.callback_query:
        await update.callback_query.answer("Access denied.", show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text("⛔ This bot is private. Access denied.")

    raise ApplicationHandlerStop


def register_access_middleware(application: Application) -> None:
    """Register middleware that runs before all other handlers."""
    application.add_handler(TypeHandler(Update, admin_only_middleware), group=-1)
