"""Multi-account selection and management handlers."""

from __future__ import annotations

import asyncio

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.handlers.common import (
    WELCOME_TEXT,
    account_picker_keyboard,
    handle_api_error,
    is_admin,
    main_menu_keyboard,
    reply_or_edit,
)
from bot.handlers.general import cancel_conversation
from bot.utils.accounts import Account, add_account, get_account, load_accounts, remove_account, validate_token_async
from bot.utils.api import clear_api_cache
from bot.utils.keyboards import markup, row, styled_button

(ACC_NAME, ACC_TOKEN) = range(2)


def _account_header(account: Account) -> str:
    return f"<b>Account:</b> <code>{account.name}</code>"


async def list_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show account picker."""
    accounts = load_accounts()
    if not accounts:
        text = (
            "<b>No API accounts configured</b>\n\n"
            "Add a Hetzner API token first."
        )
        keyboard = markup(
            row(styled_button("➕ Add Account", "acc:c", style="primary")),
        )
        await reply_or_edit(update, text, reply_markup=keyboard)
        return

    if len(accounts) == 1 and not (update.callback_query and update.callback_query.data == "acc"):
        context.user_data["account_id"] = accounts[0].id
        await reply_or_edit(
            update,
            f"{WELCOME_TEXT}\n\n{_account_header(accounts[0])}",
            reply_markup=main_menu_keyboard(),
        )
        return

    await reply_or_edit(
        update,
        "<b>Select an API account</b>\n\nChoose which Hetzner account to manage:",
        reply_markup=account_picker_keyboard(accounts, user_id=update.effective_user.id),
    )


async def select_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switch to the selected account."""
    account_id = update.callback_query.data.split(":")[2]
    account = get_account(account_id)
    if not account:
        await reply_or_edit(update, "Account not found.")
        await list_accounts(update, context)
        return

    context.user_data["account_id"] = account.id
    context.user_data.pop("force_account_picker", None)
    await reply_or_edit(
        update,
        f"{WELCOME_TEXT}\n\n{_account_header(account)}",
        reply_markup=main_menu_keyboard(),
    )


async def account_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin adding a new API account."""
    if not is_admin(update.effective_user.id):
        await reply_or_edit(update, "Only the admin can add API accounts.")
        return ConversationHandler.END

    await reply_or_edit(
        update,
        "Enter a name for this API account (e.g. Production, Staging):",
    )
    return ACC_NAME


async def account_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store account name and ask for token."""
    name = update.message.text.strip()
    if not name or len(name) > 64:
        await update.message.reply_text("Please enter a name between 1 and 64 characters.")
        return ACC_NAME

    context.user_data["acc_name"] = name
    await update.message.reply_text(
        f"Account name: <code>{name}</code>\n\nNow send the Hetzner API token:",
        parse_mode="HTML",
    )
    return ACC_TOKEN


async def account_add_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate token and save the account."""
    token = update.message.text.strip()
    name = context.user_data.get("acc_name", "")

    try:
        await validate_token_async(token)
        account = await asyncio.to_thread(add_account, name=name, token=token)
        clear_api_cache()
        context.user_data["account_id"] = account.id
        context.user_data.pop("acc_name", None)
        await update.message.reply_text(
            f"✅ Account <code>{account.name}</code> added.\n\n{WELCOME_TEXT}",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    except ValueError as exc:
        await update.message.reply_text(f"⚠️ {exc}\n\nTry a different name or /cancel.")
        return ACC_NAME
    except Exception as exc:
        await handle_api_error(update, exc)
        return ACC_TOKEN

    return ConversationHandler.END


async def account_delete_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask before deleting an account."""
    if not is_admin(update.effective_user.id):
        await reply_or_edit(update, "Only the admin can remove API accounts.")
        return

    account_id = update.callback_query.data.split(":")[2]
    account = get_account(account_id)
    if not account:
        await reply_or_edit(update, "Account not found.")
        return

    keyboard = markup(
        row(
            styled_button("✅ Delete", f"acc:dy:{account_id}", style="danger"),
            styled_button("❌ Cancel", "acc", style="primary"),
        ),
    )
    await reply_or_edit(
        update,
        f"⚠️ Remove account <code>{account.name}</code>?\nThe token will be deleted from this bot.",
        reply_markup=keyboard,
    )


async def account_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete the selected account."""
    account_id = update.callback_query.data.split(":")[2]
    removed = remove_account(account_id)
    if context.user_data.get("account_id") == account_id:
        context.user_data.pop("account_id", None)

    if removed:
        clear_api_cache(account_id)
        await reply_or_edit(update, f"✅ Account <code>{removed.name}</code> removed.")
    else:
        await reply_or_edit(update, "Account not found.")

    context.user_data.pop("force_account_picker", None)
    await list_accounts(update, context)


def register_account_handlers(application: Application) -> None:
    """Register account handlers."""
    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(account_add_start, pattern=r"^acc:c$")],
        states={
            ACC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, account_add_name)],
            ACC_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, account_add_token)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CallbackQueryHandler(cancel_conversation, pattern=r"^menu$"),
        ],
        allow_reentry=True,
        name="account_add",
        persistent=False,
    )

    application.add_handler(add_conv)
    application.add_handler(CallbackQueryHandler(list_accounts, pattern=r"^acc$"))
    application.add_handler(CallbackQueryHandler(select_account, pattern=r"^acc:s:"))
    application.add_handler(CallbackQueryHandler(account_delete_prompt, pattern=r"^acc:d:"))
    application.add_handler(CallbackQueryHandler(account_delete_confirm, pattern=r"^acc:dy:"))
