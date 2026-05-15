from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для главного меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Моя анкета", callback_data="my_profile")
    builder.button(text="🔍 Поиск пары", callback_data="search")
    builder.button(text="❤️ Мои лайки", callback_data="my_likes")
    builder.button(text="💕 Мои мэтчи", callback_data="my_matches")
    builder.adjust(1, 1, 1, 1)
    return builder.as_markup()


def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для просмотра своей анкеты (с кнопкой редактирования)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Редактировать профиль", callback_data="edit_profile")
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_menu")
    builder.adjust(1, 1)
    return builder.as_markup()


def get_search_keyboard(has_multiple_photos: bool = False, current_index: int = 0, total_photos: int = 1) -> InlineKeyboardMarkup:
    """Клавиатура для поиска (лайк/пропуск)"""
    builder = InlineKeyboardBuilder()
    if has_multiple_photos:
        builder.button(text="⬅️ Фото", callback_data="photo_prev")
        builder.button(text=f"📸 {current_index + 1}/{total_photos}", callback_data="photo_info")
        builder.button(text="Фото ➡️", callback_data="photo_next")
    builder.button(text="👎 Пропустить", callback_data="skip")
    builder.button(text="❤️ Лайк", callback_data="like")
    if has_multiple_photos:
        builder.adjust(3, 2)
    else:
        builder.adjust(2)
    return builder.as_markup()


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой назад"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_photo_done_keyboard() -> InlineKeyboardMarkup:
    """Кнопка завершения загрузки фото"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Все", callback_data="photo_done")
    builder.adjust(1)
    return builder.as_markup()


def get_edit_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для редактирования профиля"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить имя", callback_data="edit_name")
    builder.button(text="🎂 Изменить возраст", callback_data="edit_age")
    builder.button(text="👤 Изменить пол", callback_data="edit_gender")
    builder.button(text="📍 Изменить город", callback_data="edit_city")
    builder.button(text="📖 Изменить описание", callback_data="edit_bio")
    builder.button(text="📸 Изменить фото", callback_data="edit_photo")
    builder.button(text="🎯 Кого ищу", callback_data="edit_search_gender")
    builder.button(text="🔄 Создать анкету заново", callback_data="reset_profile")
    builder.button(text="⬅️ Назад к анкете", callback_data="my_profile")
    builder.adjust(1)
    return builder.as_markup()


def get_search_gender_keyboard(current: str) -> InlineKeyboardMarkup:
    """Клавиатура для выбора кого искать"""
    buttons = []
    
    male_text = "👨 Парней ✅" if current == "male" else "👨 Парней"
    female_text = "👩 Девушек ✅" if current == "female" else "👩 Девушек"
    all_text = "👥 Всех ✅" if current == "all" else "👥 Всех"
    
    builder = InlineKeyboardBuilder()
    builder.button(text=male_text, callback_data="set_search_male")
    builder.button(text=female_text, callback_data="set_search_female")
    builder.button(text=all_text, callback_data="set_search_all")
    builder.button(text="⬅️ Назад", callback_data="edit_profile")
    builder.adjust(1)
    return builder.as_markup()