import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.backend.models import User, Profile
from src.bot.keyboards import get_start_keyboard, get_back_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=get_start_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "my_profile")
async def my_profile(callback: CallbackQuery, session: AsyncSession):
    """Просмотр своей анкеты"""
    telegram_id = callback.from_user.id
    
    result = await session.execute(
        select(Profile)
        .join(User)
        .where(User.telegram_id == telegram_id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        await callback.answer("Сначала создай анкету!", show_alert=True)
        return
    
    bio_text = profile.bio if profile.bio else "Не указано"
    
    await callback.message.edit_text(
        f"👤 Твоя анкета:\n\n"
        f"Имя: {profile.name}\n"
        f"Возраст: {profile.age}\n"
        f"Пол: {'Парень' if profile.gender == 'male' else 'Девушка'}\n"
        f"Город: {profile.city or 'Не указан'}\n"
        f"О себе: {bio_text}\n\n",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "search")
async def search(callback: CallbackQuery, session: AsyncSession):
    """Поиск пары - заготовка"""
    telegram_id = callback.from_user.id
    
    # Проверяем, есть ли профиль у пользователя
    result = await session.execute(
        select(Profile)
        .join(User)
        .where(User.telegram_id == telegram_id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        await callback.answer("Сначала создай анкету в /start!", show_alert=True)
        return
    
    # TODO: Реализация поиска анкет
    await callback.message.edit_text(
        "🔍 Поиск пары...\n\n"
        "Эта функция будет доступна в следующем обновлении!\n"
        "Сейчас мы работаем над алгоритмом подбора идеальной пары для тебя. 💕",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "my_likes")
async def my_likes(callback: CallbackQuery):
    """Мои лайки - заготовка"""
    await callback.message.edit_text(
        "❤️ Твои лайки\n\n"
        "Здесь будут отображаться все пользователи, которым ты поставил лайк.\n"
        "Функция в разработке! 🔨",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "my_matches")
async def my_matches(callback: CallbackQuery):
    """Мои мэтчи - заготовка"""
    await callback.message.edit_text(
        "💕 Твои мэтчи\n\n"
        "Здесь появятся пользователи, которые ответили тебе взаимностью!\n"
        "Функция в разработке! 🔨",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()
