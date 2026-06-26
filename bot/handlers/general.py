"""General bot handlers: start, help, cancel, main menu."""

from __future__ import annotations

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

from bot.handlers.common import (
    WELCOME_TEXT,
    back_to_menu_keyboard,
    main_menu_keyboard,
    reply_or_edit,
)
from bot.utils.accounts import get_account

HELP_TEXT = (
    "<b>Help</b>\n\n"
    "• <b>Accounts</b> — switch between multiple Hetzner API keys\n"
    "• <b>Servers</b> — list, create, reboot, power on/off, set password, add SSH key, delete\n"
    "• <b>Images</b> — browse OS templates and details\n"
    "• <b>Locations</b> — view datacenter locations\n"
    "• <b>SSH Keys</b> — manage SSH keys\n\n"
    "Use /cancel anytime to stop a multi-step action."
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start."""
    from bot.handlers.account import list_accounts

    context.user_data.clear()
    await list_accounts(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help."""
    await reply_or_edit(update, HELP_TEXT, reply_markup=back_to_menu_keyboard())


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel an active conversation and return to the main menu."""
    from bot.handlers.account import list_accounts

    account_id = context.user_data.get("account_id")
    for key in ("pwd_server_id", "ssh_server_id", "acc_name", "create_name", "create_image", "create_location", "create_type", "create_images", "ssh_name"):
        context.user_data.pop(key, None)
    context.user_data.clear()
    if account_id:
        context.user_data["account_id"] = account_id
        account = get_account(account_id)
        header = f"\n\n<b>Account:</b> <code>{account.name}</code>" if account else ""
        await reply_or_edit(
            update,
            f"Action cancelled.\n\n{WELCOME_TEXT}{header}",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await list_accounts(update, context)
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /cancel and reset conversation state."""
    return await cancel_conversation(update, context)


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to the main menu."""
    from bot.handlers.account import list_accounts

    account_id = context.user_data.get("account_id")
    if not account_id:
        await list_accounts(update, context)
        return

    account = get_account(account_id)
    header = f"\n\n<b>Account:</b> <code>{account.name}</code>" if account else ""
    keys_to_keep = {"account_id", "image_filter"}
    for key in list(context.user_data):
        if key not in keys_to_keep:
            del context.user_data[key]
    await reply_or_edit(
        update,
        f"{WELCOME_TEXT}{header}",
        reply_markup=main_menu_keyboard(),
    )


def register_general_handlers(application: Application) -> None:
    """Register general command and menu handlers."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern=r"^menu$"))
