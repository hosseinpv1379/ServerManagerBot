"""SSH key management handlers."""

from __future__ import annotations

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
    back_to_menu_keyboard,
    handle_api_error,
    is_admin,
    main_menu_keyboard,
    reply_or_edit,
)
from bot.handlers.general import cancel_conversation
from bot.utils.api import get_api_for_context
from bot.utils.formatters import format_ssh_key, format_ssh_key_list
from bot.utils.keyboards import markup, row, styled_button
from bot.utils.validators import validate_ssh_key_name, validate_ssh_public_key

(SSH_NAME, SSH_KEY) = range(2)


async def list_ssh_keys(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all SSH keys."""
    try:
        keys = await get_api_for_context(context).get_ssh_keys()
        rows = [[styled_button(key.name, f"ssh:i:{key.id}", style="primary")] for key in keys]
        if is_admin(update.effective_user.id):
            rows.append([styled_button("➕ Add SSH Key", "ssh:c", style="success")])
        rows.append([styled_button("🏠 Main Menu", "menu", style="success")])
        await reply_or_edit(
            update,
            format_ssh_key_list(keys),
            reply_markup=markup(*rows),
        )
    except Exception as exc:
        await handle_api_error(update, exc)


async def ssh_key_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show SSH key details."""
    key_id = int(update.callback_query.data.split(":")[2])

    try:
        ssh_key = await get_api_for_context(context).get_ssh_key(key_id)
        if not ssh_key:
            await reply_or_edit(update, "SSH key not found.", reply_markup=back_to_menu_keyboard())
            return

        rows: list[list] = []
        if is_admin(update.effective_user.id):
            rows.append([styled_button("🗑️ Delete", f"ssh:d:{key_id}", style="danger")])
        rows.append([styled_button("◀ Back", "ssh", style="primary")])
        rows.append([styled_button("🏠 Main Menu", "menu", style="success")])

        await reply_or_edit(update, format_ssh_key(ssh_key), reply_markup=markup(*rows))
    except Exception as exc:
        await handle_api_error(update, exc)


async def ssh_delete_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask for SSH key delete confirmation."""
    if not is_admin(update.effective_user.id):
        await reply_or_edit(update, "Only the admin can delete SSH keys.", reply_markup=main_menu_keyboard())
        return

    key_id = int(update.callback_query.data.split(":")[2])
    try:
        ssh_key = await get_api_for_context(context).get_ssh_key(key_id)
        if not ssh_key:
            await reply_or_edit(update, "SSH key not found.", reply_markup=back_to_menu_keyboard())
            return

        keyboard = markup(
            row(
                styled_button("✅ Yes, delete", f"ssh:dy:{key_id}", style="danger"),
                styled_button("❌ Cancel", f"ssh:i:{key_id}", style="primary"),
            ),
        )
        await reply_or_edit(
            update,
            f"⚠️ Delete SSH key <code>{ssh_key.name}</code>?",
            reply_markup=keyboard,
        )
    except Exception as exc:
        await handle_api_error(update, exc)


async def ssh_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete SSH key after confirmation."""
    key_id = int(update.callback_query.data.split(":")[2])

    try:
        api = get_api_for_context(context)
        ssh_key = await api.get_ssh_key(key_id)
        if not ssh_key:
            await reply_or_edit(update, "SSH key not found.", reply_markup=back_to_menu_keyboard())
            return

        name = ssh_key.name
        await api.delete_ssh_key(ssh_key)
        await reply_or_edit(
            update,
            f"✅ SSH key <code>{name}</code> deleted.",
            reply_markup=back_to_menu_keyboard(),
        )
    except Exception as exc:
        await handle_api_error(update, exc)


async def ssh_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin SSH key creation."""
    if not is_admin(update.effective_user.id):
        await reply_or_edit(update, "Only the admin can add SSH keys.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    await reply_or_edit(
        update,
        "Enter a name for the SSH key:",
        reply_markup=back_to_menu_keyboard(),
    )
    return SSH_NAME


async def ssh_create_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate SSH key name and ask for public key."""
    name = update.message.text.strip()
    error = validate_ssh_key_name(name)
    if error:
        await update.message.reply_text(f"⚠️ {error}\n\nTry again or /cancel.")
        return SSH_NAME

    context.user_data["ssh_name"] = name
    await update.message.reply_text(
        f"Name: <code>{name}</code>\n\nNow send the public key:",
        parse_mode="HTML",
    )
    return SSH_KEY


async def ssh_create_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Create the SSH key."""
    public_key = update.message.text.strip()
    error = validate_ssh_public_key(public_key)
    if error:
        await update.message.reply_text(f"⚠️ {error}\n\nTry again or /cancel.")
        return SSH_KEY

    try:
        ssh_key = await get_api_for_context(context).create_ssh_key(
            name=context.user_data["ssh_name"],
            public_key=public_key,
        )
        context.user_data.pop("ssh_name", None)
        await update.message.reply_text(
            f"✅ SSH key created!\n\n{format_ssh_key(ssh_key)}",
            reply_markup=back_to_menu_keyboard(),
            parse_mode="HTML",
        )
    except Exception as exc:
        await handle_api_error(update, exc)

    return ConversationHandler.END


def register_ssh_key_handlers(application: Application) -> None:
    """Register SSH key handlers."""
    create_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ssh_create_start, pattern=r"^ssh:c$")],
        states={
            SSH_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ssh_create_name)],
            SSH_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ssh_create_key)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CallbackQueryHandler(cancel_conversation, pattern=r"^menu$"),
        ],
        allow_reentry=True,
        name="ssh_create",
        persistent=False,
    )

    application.add_handler(create_conv)
    application.add_handler(CallbackQueryHandler(list_ssh_keys, pattern=r"^ssh$"))
    application.add_handler(CallbackQueryHandler(ssh_key_info, pattern=r"^ssh:i:\d+$"))
    application.add_handler(CallbackQueryHandler(ssh_delete_prompt, pattern=r"^ssh:d:\d+$"))
    application.add_handler(CallbackQueryHandler(ssh_delete_confirm, pattern=r"^ssh:dy:\d+$"))
