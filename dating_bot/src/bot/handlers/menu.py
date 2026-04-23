import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from src.backend.models import User, Profile, Like, Match, Rating
from src.bot.keyboards import get_start_keyboard, get_back_keyboard, get_search_keyboard
from src.services.ranking import RankingService
from src.services.cache import CacheService
from src.services.rating_calculator import RatingCalculator

logger = logging.getLogger(__name__)
router = Router()
cache_service = CacheService()
ranking_service = RankingService(cache_service)
rating_calculator = RatingCalculator()

# Хранилище текущих просматриваемых профилей
current_views = {}


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    if callback.from_user.id in current_views:
        del current_views[callback.from_user.id]
    
    await callback.message.edit_text(
        "🏠 Главное меню:\n\nВыбери действие:",
        reply_markup=get_start_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "my_profile")
async def my_profile(callback: CallbackQuery, session: AsyncSession):
    """Просмотр своей анкеты"""
    telegram_id = callback.from_user.id
    
    # Явно подгружаем profile через join
    result = await session.execute(
        select(User, Profile)
        .join(Profile, User.id == Profile.user_id)
        .where(User.telegram_id == telegram_id)
    )
    row = result.first()
    
    if not row:
        await callback.answer("Сначала создай анкету!", show_alert=True)
        return
    
    user, profile = row
    
    # Получаем рейтинг
    rating_result = await session.execute(
        select(Rating).where(Rating.user_id == user.id)
    )
    rating = rating_result.scalar_one_or_none()
    
    bio_text = profile.bio if profile.bio else "Не указано"
    rating_text = f"⭐ Рейтинг: {rating.total_score:.1f}" if rating else "⭐ Рейтинг: 0"
    
    await callback.message.edit_text(
        f"👤 <b>Твоя анкета</b>\n\n"
        f"📝 Имя: {profile.name}\n"
        f"🎂 Возраст: {profile.age}\n"
        f"👤 Пол: {'👨 Парень' if profile.gender == 'male' else '👩 Девушка'}\n"
        f"📍 Город: {profile.city or 'Не указан'}\n"
        f"📖 О себе: {bio_text}\n"
        f"{rating_text}\n"
        f"📸 Фото: {profile.photos_count} шт.",
        reply_markup=get_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "search")
async def search(callback: CallbackQuery, session: AsyncSession):
    """Поиск пары с ранжированием и кэшированием"""
    logger.info(f"Поиск пары для пользователя {callback.from_user.id}")
    
    telegram_id = callback.from_user.id
    
    # Явно подгружаем profile
    result = await session.execute(
        select(User, Profile)
        .join(Profile, User.id == Profile.user_id)
        .where(User.telegram_id == telegram_id)
    )
    row = result.first()
    
    if not row:
        await callback.answer("Сначала создай анкету в /start!", show_alert=True)
        return
    
    user, user_profile = row
    
    # Проверяем кэш
    cached_profiles = await cache_service.get_cached_profiles(telegram_id)
    
    if cached_profiles and len(cached_profiles) > 0:
        profile_data = cached_profiles.pop(0)
        await cache_service.update_cache(telegram_id, cached_profiles)
        current_views[telegram_id] = profile_data['user_id']
        await show_profile(callback, profile_data)
    else:
        ranked_profiles = await ranking_service.get_ranked_profiles(
            session, user.id, user_profile
        )
        
        logger.info(f"Найдено ранжированных анкет: {len(ranked_profiles)}")
        
        if not ranked_profiles:
            await callback.message.edit_text(
                "😔 К сожалению, пока нет подходящих анкет.\n\n"
                "Попробуй позже или измени параметры поиска!",
                reply_markup=get_back_keyboard()
            )
            await callback.answer()
            return
        
        if len(ranked_profiles) > 1:
            await cache_service.cache_profiles(telegram_id, ranked_profiles[1:min(10, len(ranked_profiles))])
        
        first_profile = ranked_profiles[0]
        current_views[telegram_id] = first_profile['user_id']
        await show_profile(callback, first_profile)


async def show_profile(callback: CallbackQuery, profile_data: dict):
    """Показать анкету пользователю"""
    profile_text = (
        f"👤 <b>{profile_data['name']}</b>\n\n"
        f"🎂 Возраст: {profile_data['age']}\n"
        f"👤 Пол: {'👨 Парень' if profile_data['gender'] == 'male' else '👩 Девушка'}\n"
        f"📍 Город: {profile_data['city'] or 'Не указан'}\n"
        f"⭐ Рейтинг: {profile_data['rating']:.1f}\n\n"
    )
    
    if profile_data.get('bio'):
        profile_text += f"📖 {profile_data['bio']}\n"
    
    await callback.message.edit_text(
        profile_text,
        reply_markup=get_search_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "like")
async def like_profile(callback: CallbackQuery, session: AsyncSession):
    """Поставить лайк"""
    logger.info(f"Лайк от пользователя {callback.from_user.id}")
    
    telegram_id = callback.from_user.id
    
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    current_user = result.scalar_one_or_none()
    
    if not current_user:
        await callback.answer("Ошибка! Попробуй снова /start")
        return
    
    target_user_id = current_views.get(telegram_id)
    
    if not target_user_id:
        await callback.answer("Ошибка! Начни поиск заново", show_alert=True)
        await search(callback, session)
        return
    
    target_profile_result = await session.execute(
        select(Profile).where(Profile.user_id == target_user_id)
    )
    target_profile = target_profile_result.scalar_one_or_none()
    
    if not target_profile:
        await callback.answer("Анкета не найдена")
        await search(callback, session)
        return
    
    # Проверяем существующий лайк
    existing_like = await session.execute(
        select(Like).where(
            and_(
                Like.from_user_id == current_user.id,
                Like.to_user_id == target_user_id
            )
        )
    )
    
    if existing_like.scalar_one_or_none():
        await callback.answer("Ты уже лайкнул эту анкету!", show_alert=True)
        await search(callback, session)
        return
    
    # Создаём лайк
    like = Like(
        from_user_id=current_user.id,
        to_user_id=target_user_id
    )
    session.add(like)
    await session.commit()
    
    # Проверяем взаимный лайк
    mutual_like = await session.execute(
        select(Like).where(
            and_(
                Like.from_user_id == target_user_id,
                Like.to_user_id == current_user.id
            )
        )
    )
    
    if mutual_like.scalar_one_or_none():
        match = Match(
            user1_id=min(current_user.id, target_user_id),
            user2_id=max(current_user.id, target_user_id)
        )
        session.add(match)
        await session.commit()
        
        await callback.message.answer(
            f"💕 <b>Это взаимно!</b> 💕\n\n"
            f"Ты и {target_profile.name} понравились друг другу!\n"
            f"Напиши первым/первой!",
            parse_mode="HTML"
        )
    else:
        await callback.answer("❤️ Лайк поставлен!")
    
    # Обновляем рейтинги
    await rating_calculator.update_rating(session, current_user.id)
    await rating_calculator.update_rating(session, target_user_id)
    
    await cache_service.clear_cache(telegram_id)
    await search(callback, session)


@router.callback_query(F.data == "skip")
async def skip_profile(callback: CallbackQuery, session: AsyncSession):
    """Пропустить анкету"""
    logger.info(f"Пропуск от пользователя {callback.from_user.id}")
    await callback.answer("👎 Пропущено")
    await cache_service.clear_cache(callback.from_user.id)
    await search(callback, session)


@router.callback_query(F.data == "my_likes")
async def my_likes(callback: CallbackQuery, session: AsyncSession):
    """Мои лайки"""
    result = await session.execute(
        select(User).where(User.telegram_id == callback.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("Сначала создай анкету!", show_alert=True)
        return
    
    likes_result = await session.execute(
        select(Like, Profile)
        .join(Profile, Like.to_user_id == Profile.user_id)
        .where(Like.from_user_id == user.id)
        .order_by(Like.created_at.desc())
        .limit(10)
    )
    likes = likes_result.all()
    
    if not likes:
        await callback.message.edit_text(
            "❤️ <b>Твои лайки</b>\n\n"
            "Ты ещё никому не поставил лайк. Начни поиск пары!",
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    likes_text = "❤️ <b>Твои лайки</b>\n\n"
    for like, profile in likes:
        likes_text += f"• {profile.name}, {profile.age} лет\n"
    
    await callback.message.edit_text(
        likes_text,
        reply_markup=get_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "my_matches")
async def my_matches(callback: CallbackQuery, session: AsyncSession):
    """Мои мэтчи"""
    result = await session.execute(
        select(User).where(User.telegram_id == callback.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("Сначала создай анкету!", show_alert=True)
        return
    
    matches_result = await session.execute(
        select(Match, Profile)
        .join(Profile, 
              (Match.user1_id == Profile.user_id) | (Match.user2_id == Profile.user_id))
        .where(
            and_(
                (Match.user1_id == user.id) | (Match.user2_id == user.id),
                Profile.user_id != user.id
            )
        )
        .order_by(Match.created_at.desc())
        .limit(10)
    )
    matches = matches_result.all()
    
    if not matches:
        await callback.message.edit_text(
            "💕 <b>Твои мэтчи</b>\n\n"
            "У тебя пока нет мэтчей. Продолжай лайкать анкеты!",
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    matches_text = "💕 <b>Твои мэтчи</b>\n\n"
    for match, profile in matches:
        matches_text += f"• {profile.name}, {profile.age} лет\n"
    
    await callback.message.edit_text(
        matches_text,
        reply_markup=get_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()