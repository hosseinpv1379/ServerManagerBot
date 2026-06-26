"""Image management handlers."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from bot.config import PAGE_SIZE
from bot.handlers.common import back_to_menu_keyboard, handle_api_error, paginate_keyboard, reply_or_edit
from bot.utils.api import get_api_for_context
from bot.utils.formatters import format_image, format_image_list
from bot.utils.keyboards import markup, row, styled_button

OS_FILTERS = ["ubuntu", "debian", "fedora", "centos", "rocky", "alma"]


async def filter_images(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Apply OS filter to image list."""
    os_name = update.callback_query.data.split(":")[2]
    context.user_data["image_filter"] = os_name
    await _list_images_page(update, context, page=0)


async def clear_image_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear OS filter."""
    context.user_data.pop("image_filter", None)
    await _list_images_page(update, context, page=0)


async def list_images(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show paginated image list."""
    query = update.callback_query
    page = int(query.data.split(":")[1]) if query and query.data else 0
    await _list_images_page(update, context, page=page)


async def _list_images_page(update: Update, context: ContextTypes.DEFAULT_TYPE, *, page: int) -> None:
    """Render a paginated image list."""
    os_filter = context.user_data.get("image_filter")

    try:
        images = await get_api_for_context(context).get_images(os_filter=os_filter)
        header = f" (filter: {os_filter})" if os_filter else ""
        text = format_image_list(images, page=page, page_size=PAGE_SIZE).replace(
            "<b>Images</b>", f"<b>Images</b>{header}", 1
        )
        filter_row = [
            styled_button(
                f"{'✓ ' if os_filter == name else ''}{name.title()}",
                f"img:f:{name}",
                style="primary" if os_filter == name else None,
            )
            for name in OS_FILTERS[:3]
        ]
        filter_row2 = [
            styled_button(
                f"{'✓ ' if os_filter == name else ''}{name.title()}",
                f"img:f:{name}",
                style="primary" if os_filter == name else None,
            )
            for name in OS_FILTERS[3:]
        ]
        extra_rows = [
            filter_row,
            filter_row2,
            [styled_button("Clear filter", "img:clr")],
        ]
        keyboard = paginate_keyboard(
            items=images,
            page=page,
            prefix="img",
            item_label=lambda img: (img.name or img.description or str(img.id))[:40],
            item_callback=lambda img: f"img:i:{img.id}",
            extra_rows=extra_rows,
        )
        await reply_or_edit(update, text, reply_markup=keyboard)
    except Exception as exc:
        await handle_api_error(update, exc)


async def image_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show image details."""
    image_id = int(update.callback_query.data.split(":")[2])

    try:
        image = await get_api_for_context(context).get_image(image_id)
        if not image:
            await reply_or_edit(update, "Image not found.", reply_markup=back_to_menu_keyboard())
            return

        keyboard = markup(
            row(styled_button("◀ Back", "img:0", style="primary")),
            row(styled_button("🏠 Main Menu", "menu", style="success")),
        )
        await reply_or_edit(update, format_image(image), reply_markup=keyboard)
    except Exception as exc:
        await handle_api_error(update, exc)


def register_image_handlers(application: Application) -> None:
    """Register image handlers."""
    application.add_handler(CallbackQueryHandler(list_images, pattern=r"^img:\d+$"))
    application.add_handler(CallbackQueryHandler(filter_images, pattern=r"^img:f:"))
    application.add_handler(CallbackQueryHandler(clear_image_filter, pattern=r"^img:clr$"))
    application.add_handler(CallbackQueryHandler(image_info, pattern=r"^img:i:\d+$"))
