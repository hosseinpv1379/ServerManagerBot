"""Styled inline keyboard helpers."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def styled_button(
    text: str,
    callback_data: str,
    *,
    style: str | None = None,
) -> InlineKeyboardButton:
    """Create an inline button with optional Telegram style."""
    if style:
        return InlineKeyboardButton(text, callback_data=callback_data, api_kwargs={"style": style})
    return InlineKeyboardButton(text, callback_data=callback_data)


def row(*buttons: InlineKeyboardButton) -> list[InlineKeyboardButton]:
    """Build a keyboard row."""
    return list(buttons)


def markup(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    """Build an inline keyboard markup."""
    return InlineKeyboardMarkup(list(rows))
