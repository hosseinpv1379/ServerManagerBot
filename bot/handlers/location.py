"""Location management handlers."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from bot.handlers.common import back_to_menu_keyboard, handle_api_error, reply_or_edit
from bot.utils.api import get_api_for_context
from bot.utils.formatters import format_location, format_location_list
from bot.utils.keyboards import markup, row, styled_button


async def list_locations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all Hetzner locations."""
    try:
        locations = await get_api_for_context(context).get_locations()
        rows = [
            [styled_button(f"{loc.name} — {loc.city}", f"loc:i:{loc.id}", style="primary")]
            for loc in locations
        ]
        rows.append([styled_button("🏠 Main Menu", "menu", style="success")])
        await reply_or_edit(
            update,
            format_location_list(locations),
            reply_markup=markup(*rows),
        )
    except Exception as exc:
        await handle_api_error(update, exc)


async def location_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show location details."""
    location_id = int(update.callback_query.data.split(":")[2])

    try:
        location = await get_api_for_context(context).get_location(location_id)
        if not location:
            await reply_or_edit(update, "Location not found.", reply_markup=back_to_menu_keyboard())
            return

        keyboard = markup(
            row(styled_button("◀ Back", "loc", style="primary")),
            row(styled_button("🏠 Main Menu", "menu", style="success")),
        )
        await reply_or_edit(update, format_location(location), reply_markup=keyboard)
    except Exception as exc:
        await handle_api_error(update, exc)


def register_location_handlers(application: Application) -> None:
    """Register location handlers."""
    application.add_handler(CallbackQueryHandler(list_locations, pattern=r"^loc$"))
    application.add_handler(CallbackQueryHandler(location_info, pattern=r"^loc:i:\d+$"))
