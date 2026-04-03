from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для главного меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Моя анкета", callback_data="my_profile")
    builder.button(text="🔍 Поиск пары", callback_data="search")
    builder.button(text="❤️ Мои лайки", callback_data="my_likes")
    builder.button(text=" Мои мэтчи", callback_data="my_matches")
    builder.adjust(1, 1, 1, 1)
    return builder.as_markup()


def get_search_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для поиска (лайк/пропуск)"""
    builder = InlineKeyboardBuilder()
    builder.button(text=" Пропустить", callback_data="skip")
    builder.button(text="❤️ Лайк", callback_data="like")
    builder.adjust(2)
    return builder.as_markup()


def get_profile_keyboard(profile_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра профиля"""
    builder = InlineKeyboardBuilder()
    builder.button(text="️ Назад", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой назад"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()
