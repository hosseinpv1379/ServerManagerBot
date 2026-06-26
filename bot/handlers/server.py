"""Server management handlers."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config import PAGE_SIZE
from bot.handlers.common import (
    back_to_menu_keyboard,
    handle_api_error,
    is_admin,
    main_menu_keyboard,
    paginate_keyboard,
    reply_or_edit,
    server_actions_keyboard,
)
from bot.handlers.general import cancel_conversation
from bot.services.server_access import install_public_key_on_server, set_custom_root_password
from bot.utils.api import get_api_for_context
from bot.utils.formatters import format_server, format_server_list
from bot.utils.keyboards import markup, row, styled_button
from bot.utils.ssh_client import SSHError
from bot.utils.validators import validate_root_password, validate_server_name, validate_ssh_public_key

logger = logging.getLogger(__name__)

(
    CREATE_NAME,
    CREATE_IMAGE,
    CREATE_LOCATION,
    CREATE_TYPE,
    CREATE_CONFIRM,
    SET_PASSWORD,
    ADD_SSH_KEY,
) = range(7)


def _server_result_keyboard(server_id: int) -> InlineKeyboardMarkup:
    """Keyboard shown after a successful server SSH operation."""
    return markup(
        row(styled_button("◀ Back to Server", f"srv:i:{server_id}", style="primary")),
        row(styled_button("🏠 Main Menu", "menu", style="success")),
    )


async def list_servers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show paginated server list."""
    query = update.callback_query
    page = int(query.data.split(":")[1]) if query and query.data else 0

    try:
        servers = await get_api_for_context(context).get_servers()
        text = format_server_list(servers, page=page, page_size=PAGE_SIZE)
        keyboard = paginate_keyboard(
            items=servers,
            page=page,
            prefix="srv",
            item_label=lambda s: f"{s.name} [{s.status}]",
            item_callback=lambda s: f"srv:i:{s.id}",
            extra_rows=[[styled_button("➕ Create Server", "srv:c", style="success")]],
        )
        await reply_or_edit(update, text, reply_markup=keyboard)
    except Exception as exc:
        await handle_api_error(update, exc)


async def server_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show server details and action buttons."""
    server_id = int(update.callback_query.data.split(":")[2])

    try:
        server = await get_api_for_context(context).get_server(server_id)
        if not server:
            await reply_or_edit(update, "Server not found.", reply_markup=back_to_menu_keyboard())
            return

        await reply_or_edit(
            update,
            format_server(server),
            reply_markup=server_actions_keyboard(server_id),
        )
    except Exception as exc:
        await handle_api_error(update, exc)


async def server_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle reboot, power on, and power off actions."""
    parts = update.callback_query.data.split(":")
    action, server_id = parts[1], int(parts[2])
    labels = {"r": "Rebooting", "on": "Powering on", "off": "Powering off"}
    label = labels.get(action, "Working")

    try:
        api = get_api_for_context(context)
        server = await api.get_server(server_id)
        if not server:
            await reply_or_edit(update, "Server not found.", reply_markup=back_to_menu_keyboard())
            return

        await reply_or_edit(update, f"⏳ {label} <code>{server.name}</code>...")

        if action == "r":
            await api.reboot_server(server)
        elif action == "on":
            await api.power_on_server(server)
        elif action == "off":
            await api.power_off_server(server)

        server = await api.get_server(server_id)
        await reply_or_edit(
            update,
            f"✅ Action completed.\n\n{format_server(server)}",
            reply_markup=markup(
                row(styled_button("◀ Back to Server", f"srv:i:{server_id}", style="primary")),
                row(styled_button("🏠 Main Menu", "menu", style="success")),
            ),
        )
    except Exception as exc:
        await handle_api_error(update, exc)


async def cancel_to_server(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel SSH/password flow and return to server details."""
    server_id = context.user_data.pop("pwd_server_id", None) or context.user_data.pop("ssh_server_id", None)
    if server_id and update.callback_query:
        update.callback_query.data = f"srv:i:{server_id}"
        await server_info(update, context)
    else:
        await cancel_conversation(update, context)
    return ConversationHandler.END


async def set_password_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin custom root password setup."""
    server_id = int(update.callback_query.data.split(":")[2])
    context.user_data["pwd_server_id"] = server_id

    try:
        server = await get_api_for_context(context).get_server(server_id)
        if not server:
            await reply_or_edit(update, "Server not found.", reply_markup=back_to_menu_keyboard())
            return ConversationHandler.END

        await reply_or_edit(
            update,
            f"Set root password for <code>{server.name}</code>\n\n"
            "Send the new root password (min 8 characters).\n\n"
            "The bot will:\n"
            "1. Reset password via Hetzner API\n"
            "2. Connect via SSH\n"
            "3. Apply your chosen password",
            reply_markup=markup(row(styled_button("❌ Cancel", f"srv:i:{server_id}", style="danger"))),
        )
        return SET_PASSWORD
    except Exception as exc:
        await handle_api_error(update, exc)
        return ConversationHandler.END


async def set_password_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Apply the custom root password via SSH."""
    new_password = update.message.text
    error = validate_root_password(new_password)
    if error:
        await update.message.reply_text(f"⚠️ {error}\n\nTry again or /cancel.")
        return SET_PASSWORD

    server_id = context.user_data.get("pwd_server_id")
    if not server_id:
        await update.message.reply_text("Session expired. Use /start and try again.")
        return ConversationHandler.END

    status = await update.message.reply_text(
        "⏳ Resetting password via Hetzner, connecting via SSH, applying your password...",
        parse_mode="HTML",
    )

    try:
        api = get_api_for_context(context)
        server = await api.get_server(server_id)
        if not server:
            await status.edit_text("Server not found.", reply_markup=back_to_menu_keyboard())
            return ConversationHandler.END

        server = await set_custom_root_password(api, server, new_password.strip())
        context.user_data.pop("pwd_server_id", None)

        text = (
            "✅ Root password set successfully.\n\n"
            f"{format_server(server)}\n\n"
            f"<b>Your root password:</b> <code>{new_password.strip()}</code>"
        )
        await status.edit_text(text, reply_markup=_server_result_keyboard(server_id), parse_mode="HTML")
    except SSHError as exc:
        await status.edit_text(f"⚠️ SSH error: {exc}", reply_markup=_server_result_keyboard(server_id))
    except Exception as exc:
        await handle_api_error(update, exc)

    return ConversationHandler.END


async def add_ssh_key_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin SSH public key installation on the server."""
    server_id = int(update.callback_query.data.split(":")[2])
    context.user_data["ssh_server_id"] = server_id

    try:
        server = await get_api_for_context(context).get_server(server_id)
        if not server:
            await reply_or_edit(update, "Server not found.", reply_markup=back_to_menu_keyboard())
            return ConversationHandler.END

        await reply_or_edit(
            update,
            f"Add SSH public key to <code>{server.name}</code>\n\n"
            "Send the public key (ssh-rsa, ssh-ed25519, or ecdsa).\n\n"
            "The bot will:\n"
            "1. Reset password via Hetzner API\n"
            "2. Connect via SSH as root\n"
            "3. Add the key to <code>/root/.ssh/authorized_keys</code>",
            reply_markup=markup(row(styled_button("❌ Cancel", f"srv:i:{server_id}", style="danger"))),
        )
        return ADD_SSH_KEY
    except Exception as exc:
        await handle_api_error(update, exc)
        return ConversationHandler.END


async def add_ssh_key_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Install the public key on the server via SSH."""
    public_key = update.message.text.strip()
    error = validate_ssh_public_key(public_key)
    if error:
        await update.message.reply_text(f"⚠️ {error}\n\nTry again or /cancel.")
        return ADD_SSH_KEY

    server_id = context.user_data.get("ssh_server_id")
    if not server_id:
        await update.message.reply_text("Session expired. Use /start and try again.")
        return ConversationHandler.END

    status = await update.message.reply_text(
        "⏳ Resetting password via Hetzner, connecting via SSH, installing key...",
        parse_mode="HTML",
    )

    try:
        api = get_api_for_context(context)
        server = await api.get_server(server_id)
        if not server:
            await status.edit_text("Server not found.", reply_markup=back_to_menu_keyboard())
            return ConversationHandler.END

        server, temp_password, added = await install_public_key_on_server(api, server, public_key)
        context.user_data.pop("ssh_server_id", None)

        key_status = "Key added to server." if added else "Key was already on the server."
        text = (
            f"✅ {key_status}\n\n"
            f"{format_server(server)}\n\n"
            f"<b>Temporary root password</b> (from Hetzner reset):\n"
            f"<code>{temp_password}</code>\n\n"
            "You can now connect with your SSH key or this password."
        )
        await status.edit_text(text, reply_markup=_server_result_keyboard(server_id), parse_mode="HTML")
    except SSHError as exc:
        await status.edit_text(f"⚠️ SSH error: {exc}", reply_markup=_server_result_keyboard(server_id))
    except Exception as exc:
        await handle_api_error(update, exc)

    return ConversationHandler.END


async def server_delete_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask for delete confirmation."""
    server_id = int(update.callback_query.data.split(":")[2])

    try:
        server = await get_api_for_context(context).get_server(server_id)
        if not server:
            await reply_or_edit(update, "Server not found.", reply_markup=back_to_menu_keyboard())
            return

        keyboard = markup(
            row(
                styled_button("✅ Yes, delete", f"srv:dy:{server_id}", style="danger"),
                styled_button("❌ Cancel", f"srv:i:{server_id}", style="primary"),
            ),
        )
        await reply_or_edit(
            update,
            f"⚠️ Delete server <code>{server.name}</code>?\nThis cannot be undone.",
            reply_markup=keyboard,
        )
    except Exception as exc:
        await handle_api_error(update, exc)


async def server_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete the server after confirmation."""
    server_id = int(update.callback_query.data.split(":")[2])

    try:
        api = get_api_for_context(context)
        server = await api.get_server(server_id)
        if not server:
            await reply_or_edit(update, "Server not found.", reply_markup=back_to_menu_keyboard())
            return

        name = server.name
        await reply_or_edit(update, f"⏳ Deleting <code>{name}</code>...")
        await api.delete_server(server)
        await reply_or_edit(
            update,
            f"✅ Server <code>{name}</code> deleted.",
            reply_markup=back_to_menu_keyboard(),
        )
    except Exception as exc:
        await handle_api_error(update, exc)


async def create_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin server creation flow."""
    if not is_admin(update.effective_user.id):
        await reply_or_edit(update, "Only the admin can create servers.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    await reply_or_edit(
        update,
        "Enter a server name (3-63 characters, letters, numbers, hyphens):",
        reply_markup=back_to_menu_keyboard(),
    )
    return CREATE_NAME


async def create_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate server name and show image selection."""
    name = update.message.text.strip()
    error = validate_server_name(name)
    if error:
        await update.message.reply_text(f"⚠️ {error}\n\nTry again or /cancel.")
        return CREATE_NAME

    context.user_data["create_name"] = name

    try:
        images = await get_api_for_context(context).get_images()
        if not images:
            await update.message.reply_text("No images available.", reply_markup=back_to_menu_keyboard())
            return ConversationHandler.END

        context.user_data["create_images"] = {str(img.id): img for img in images}
        rows = [
            [styled_button(img.name or img.description or str(img.id), f"srv:ci:{img.id}", style="primary")]
            for img in images[:PAGE_SIZE]
        ]
        if len(images) > PAGE_SIZE:
            rows.append([styled_button("More images in Images menu", "img:0")])
        rows.append([styled_button("❌ Cancel", "menu", style="danger")])
        await update.message.reply_text(
            f"Selected name: <code>{name}</code>\n\nChoose an image:",
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode="HTML",
        )
        return CREATE_IMAGE
    except Exception as exc:
        await handle_api_error(update, exc)
        return ConversationHandler.END


async def create_select_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store selected image and show locations."""
    image_id = update.callback_query.data.split(":")[2]
    images = context.user_data.get("create_images", {})
    image = images.get(image_id)
    if not image:
        await reply_or_edit(update, "Image not found. Start again from the menu.")
        return ConversationHandler.END

    context.user_data["create_image"] = image.name or image.description

    try:
        locations = await get_api_for_context(context).get_locations()
        rows = [
            [styled_button(f"{loc.name} — {loc.city}", f"srv:cl:{loc.name}", style="primary")]
            for loc in locations
        ]
        rows.append([styled_button("❌ Cancel", "menu", style="danger")])
        await reply_or_edit(
            update,
            f"Image: <code>{context.user_data['create_image']}</code>\n\nChoose a location:",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return CREATE_LOCATION
    except Exception as exc:
        await handle_api_error(update, exc)
        return ConversationHandler.END


async def create_select_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store selected location and show server types."""
    location_name = update.callback_query.data.split(":")[2]
    context.user_data["create_location"] = location_name

    try:
        server_types = await get_api_for_context(context).get_server_types()
        rows = [
            [
                styled_button(
                    f"{st.name} — {st.cores}c / {st.memory}GB / {st.disk}GB",
                    f"srv:ct:{st.name}",
                    style="primary",
                )
            ]
            for st in server_types[:10]
        ]
        rows.append([styled_button("❌ Cancel", "menu", style="danger")])
        await reply_or_edit(
            update,
            f"Location: <code>{location_name}</code>\n\nChoose a server type:",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return CREATE_TYPE
    except Exception as exc:
        await handle_api_error(update, exc)
        return ConversationHandler.END


async def create_select_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store server type and show confirmation."""
    type_name = update.callback_query.data.split(":")[2]
    context.user_data["create_type"] = type_name

    summary = (
        "<b>Confirm server creation</b>\n\n"
        f"<b>Name:</b> <code>{context.user_data['create_name']}</code>\n"
        f"<b>Image:</b> <code>{context.user_data['create_image']}</code>\n"
        f"<b>Location:</b> <code>{context.user_data['create_location']}</code>\n"
        f"<b>Type:</b> <code>{type_name}</code>"
    )
    keyboard = markup(
        row(
            styled_button("✅ Create", "srv:cf", style="success"),
            styled_button("❌ Cancel", "menu", style="danger"),
        ),
    )
    await reply_or_edit(update, summary, reply_markup=keyboard)
    return CREATE_CONFIRM


async def create_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Create the server."""
    await reply_or_edit(update, "⏳ Creating server, please wait...")

    try:
        server, root_password = await get_api_for_context(context).create_server(
            name=context.user_data["create_name"],
            server_type_name=context.user_data["create_type"],
            image_name=context.user_data["create_image"],
            location_name=context.user_data["create_location"],
        )
        text = f"✅ Server created!\n\n{format_server(server)}"
        if root_password:
            text += f"\n\n<b>Root password:</b> <code>{root_password}</code>"
        keyboard = markup(
            row(styled_button("View Server", f"srv:i:{server.id}", style="primary")),
            row(styled_button("🏠 Main Menu", "menu", style="success")),
        )
        for key in ("create_name", "create_image", "create_location", "create_type", "create_images"):
            context.user_data.pop(key, None)
        await reply_or_edit(update, text, reply_markup=keyboard)
    except Exception as exc:
        await handle_api_error(update, exc)

    return ConversationHandler.END


def register_server_handlers(application: Application) -> None:
    """Register server management handlers."""
    create_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_start, pattern=r"^srv:c$")],
        states={
            CREATE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_name)],
            CREATE_IMAGE: [CallbackQueryHandler(create_select_image, pattern=r"^srv:ci:")],
            CREATE_LOCATION: [CallbackQueryHandler(create_select_location, pattern=r"^srv:cl:")],
            CREATE_TYPE: [CallbackQueryHandler(create_select_type, pattern=r"^srv:ct:")],
            CREATE_CONFIRM: [CallbackQueryHandler(create_confirm, pattern=r"^srv:cf$")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CallbackQueryHandler(cancel_conversation, pattern=r"^menu$"),
        ],
        allow_reentry=True,
        name="server_create",
        persistent=False,
    )

    application.add_handler(create_conv)

    set_password_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_password_start, pattern=r"^srv:sp:\d+$")],
        states={
            SET_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_password_input)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CallbackQueryHandler(cancel_conversation, pattern=r"^menu$"),
            CallbackQueryHandler(cancel_to_server, pattern=r"^srv:i:\d+$"),
        ],
        allow_reentry=True,
        name="server_set_password",
        persistent=False,
    )

    add_ssh_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_ssh_key_start, pattern=r"^srv:sk:\d+$")],
        states={
            ADD_SSH_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_ssh_key_input)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CallbackQueryHandler(cancel_conversation, pattern=r"^menu$"),
            CallbackQueryHandler(cancel_to_server, pattern=r"^srv:i:\d+$"),
        ],
        allow_reentry=True,
        name="server_add_ssh",
        persistent=False,
    )

    application.add_handler(set_password_conv)
    application.add_handler(add_ssh_conv)
    application.add_handler(CallbackQueryHandler(list_servers, pattern=r"^srv:\d+$"))
    application.add_handler(CallbackQueryHandler(server_info, pattern=r"^srv:i:\d+$"))
    application.add_handler(CallbackQueryHandler(server_action, pattern=r"^srv:(r|on|off):\d+$"))
    application.add_handler(CallbackQueryHandler(server_delete_prompt, pattern=r"^srv:d:\d+$"))
    application.add_handler(CallbackQueryHandler(server_delete_confirm, pattern=r"^srv:dy:\d+$"))
