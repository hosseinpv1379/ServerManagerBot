"""Shared handler utilities."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import ADMIN_USER_IDS, PAGE_SIZE
from bot.utils.accounts import Account
from bot.utils.api import HetznerAPIError
from bot.utils.keyboards import markup, row, styled_button

WELCOME_TEXT = (
    "<b>Hetzner Cloud Manager</b>\n\n"
    "Manage your Hetzner Cloud servers, images, locations, and SSH keys.\n"
    "Choose an option below."
)


def is_admin(user_id: int) -> bool:
    """Return True when the user is an allowed admin."""
    return user_id in ADMIN_USER_IDS


def require_account(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Return selected account id or None."""
    return context.user_data.get("account_id")


async def deny_access(update: Update) -> None:
    """Notify the user that access is denied."""
    if update.callback_query:
        await update.callback_query.answer("Access denied.", show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text("Access denied.")


async def reply_or_edit(
    update: Update,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str = "HTML",
) -> None:
    """Edit callback message or reply to a command/message."""
    if update.callback_query and update.callback_query.message:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        return
    if update.effective_message:
        await update.effective_message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )


async def handle_api_error(update: Update, exc: Exception) -> None:
    """Show a user-friendly API error."""
    message = str(exc) if isinstance(exc, HetznerAPIError) else "Something went wrong. Please try again."
    await reply_or_edit(update, f"⚠️ {message}")


def paginate_keyboard(
    *,
    items: list[Any],
    page: int,
    prefix: str,
    item_label: Callable[[Any], str],
    item_callback: Callable[[Any], str],
    extra_rows: list[list[InlineKeyboardButton]] | None = None,
) -> InlineKeyboardMarkup:
    """Build a paginated inline keyboard."""
    start = page * PAGE_SIZE
    page_items = items[start : start + PAGE_SIZE]
    rows: list[list[InlineKeyboardButton]] = []

    for item in page_items:
        rows.append([styled_button(item_label(item), item_callback(item), style="primary")])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(styled_button("◀ Prev", f"{prefix}:{page - 1}"))
    if start + PAGE_SIZE < len(items):
        nav.append(styled_button("Next ▶", f"{prefix}:{page + 1}"))
    if nav:
        rows.append(nav)

    if extra_rows:
        rows.extend(extra_rows)

    rows.append([styled_button("🏠 Main Menu", "menu", style="success")])
    return InlineKeyboardMarkup(rows)


def account_picker_keyboard(accounts: list[Account], *, user_id: int) -> InlineKeyboardMarkup:
    """Build the account selection keyboard."""
    rows: list[list[InlineKeyboardButton]] = [
        [styled_button(f"🔑 {account.name}", f"acc:s:{account.id}", style="primary")]
        for account in accounts
    ]
    if is_admin(user_id):
        rows.append([styled_button("➕ Add Account", "acc:c", style="success")])
        for account in accounts:
            rows.append([styled_button(f"🗑 Remove {account.name}", f"acc:d:{account.id}", style="danger")])
    return InlineKeyboardMarkup(rows)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Return the main menu keyboard."""
    return markup(
        row(styled_button("🖥️ Servers", "srv:0", style="primary")),
        row(
            styled_button("🖼️ Images", "img:0", style="primary"),
            styled_button("🌍 Locations", "loc", style="primary"),
        ),
        row(styled_button("🔑 SSH Keys", "ssh", style="primary")),
        row(
            styled_button("🔄 Switch Account", "acc", style="success"),
        ),
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Return a keyboard with only the main menu button."""
    return markup(row(styled_button("🏠 Main Menu", "menu", style="success")))


def server_actions_keyboard(server_id: int) -> InlineKeyboardMarkup:
    """Return action buttons for a server detail view."""
    return markup(
        row(
            styled_button("🔄 Reboot", f"srv:r:{server_id}", style="primary"),
            styled_button("⚡ Power On", f"srv:on:{server_id}", style="success"),
        ),
        row(
            styled_button("🔌 Power Off", f"srv:off:{server_id}"),
            styled_button("🔑 Set Password", f"srv:sp:{server_id}", style="primary"),
        ),
        row(styled_button("🔐 Add SSH Key", f"srv:sk:{server_id}", style="success")),
        row(styled_button("🗑️ Delete", f"srv:d:{server_id}", style="danger")),
        row(
            styled_button("◀ Back", "srv:0"),
            styled_button("🏠 Main Menu", "menu", style="success"),
        ),
    )
