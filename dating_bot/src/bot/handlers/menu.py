import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, User as TgUser
from aiogram.utils.formatting import Text, TextMention
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete

from src.backend.models import User, Profile, ProfilePhoto, Like, Match, Rating
from src.bot.keyboards import get_start_keyboard, get_back_keyboard, get_search_keyboard, get_profile_keyboard, get_edit_keyboard, get_search_gender_keyboard, get_photo_done_keyboard
from src.services.ranking import RankingService
from src.services.cache import CacheService
from src.services.rating_calculator import RatingCalculator
from src.services.event_publisher import publish_like_event, publish_match_event

logger = logging.getLogger(__name__)
router = Router()
cache_service = CacheService()
ranking_service = RankingService(cache_service)
rating_calculator = RatingCalculator()

# Текущая анкета и индекс фото — в памяти процесса (короткая сессия просмотра)
user_current_profiles = {}  # {telegram_id: profile_data}
user_current_photo_index = {}  # {telegram_id: int}


class EditProfileForm(StatesGroup):
    """Состояния для редактирования анкеты"""
    city = State()
    bio = State()
    photo = State()


async def get_profile_text(profile_data: dict) -> str:
    """Получить текст анкеты"""
    gender_emoji = "👨" if profile_data['gender'] == 'male' else "👩"
    gender_text = "Парень" if profile_data['gender'] == 'male' else "Девушка"
    
    profile_text = (
        f"👤 <b>{profile_data['name']}</b>\n\n"
        f"🎂 Возраст: {profile_data['age']}\n"
        f"👤 Пол: {gender_emoji} {gender_text}\n"
        f"📍 Город: {profile_data['city'] or 'Не указан'}\n"
        f"⭐ Рейтинг: {profile_data['rating']:.1f}\n\n"
    )
    
    if profile_data.get('bio'):
        profile_text += f"📖 {profile_data['bio']}\n"
    
    return profile_text


async def _send_match_notification(bot, recipient_chat_id: int, partner_telegram_id: int, partner_name: str) -> None:
    """Уведомление о мэтче: кликабельное имя (text_mention) + кнопка «Написать»."""
    partner_url = f"tg://user?id={partner_telegram_id}"
    try:
        partner_chat = await bot.get_chat(partner_telegram_id)
        if partner_chat.username:
            partner_url = f"https://t.me/{partner_chat.username}"
    except Exception as e:
        logger.warning("Не удалось получить username для %s: %s", partner_telegram_id, e)

    partner_user = TgUser(id=partner_telegram_id, is_bot=False, first_name=partner_name)
    content = Text(
        "💘 У вас взаимный мэтч с ",
        TextMention(partner_name, user=partner_user),
        "! Нажми на имя или кнопку ниже, чтобы написать.",
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"💬 Написать {partner_name}", url=partner_url)]
        ]
    )
    await bot.send_message(
        chat_id=recipient_chat_id,
        reply_markup=keyboard,
        **content.as_kwargs(),
    )


async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
    """Безопасное редактирование сообщения с обработкой ошибок"""
    try:
        if reply_markup:
            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await callback.message.edit_text(text, parse_mode=parse_mode)
    except Exception as e:
        if "message to edit not found" in str(e) or "message is not modified" in str(e):
            pass
        else:
            try:
                if reply_markup:
                    await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
                else:
                    await callback.message.answer(text, parse_mode=parse_mode)
            except:
                pass


async def _get_profile_photo_ids(session: AsyncSession, profile_user_id: int, fallback_photo_id: str | None) -> list[str]:
    photos_result = await session.execute(
        select(ProfilePhoto.file_id, ProfilePhoto.position)
        .join(Profile, ProfilePhoto.profile_id == Profile.id)
        .where(Profile.user_id == profile_user_id)
        .order_by(ProfilePhoto.position.asc())
    )
    photo_ids = [row[0] for row in photos_result.all()]
    if not photo_ids and fallback_photo_id:
        photo_ids = [fallback_photo_id]
    return photo_ids


async def _render_profile_message(callback: CallbackQuery, profile_data: dict):
    telegram_id = callback.from_user.id
    photo_ids = profile_data.get("photo_ids") or []
    current_idx = user_current_photo_index.get(telegram_id, 0)
    if current_idx >= len(photo_ids):
        current_idx = 0
    user_current_photo_index[telegram_id] = current_idx

    profile_text = await get_profile_text(profile_data)
    keyboard = get_search_keyboard(
        has_multiple_photos=len(photo_ids) > 1,
        current_index=current_idx,
        total_photos=max(len(photo_ids), 1)
    )

    if photo_ids:
        media = InputMediaPhoto(media=photo_ids[current_idx], caption=profile_text, parse_mode="HTML")
        try:
            await callback.message.edit_media(media=media, reply_markup=keyboard)
        except Exception:
            await callback.message.answer_photo(photo=photo_ids[current_idx], caption=profile_text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await safe_edit_message(callback, profile_text, keyboard, "HTML")


async def show_profile(callback: CallbackQuery, profile_data: dict):
    """Показать анкету пользователю"""
    user_current_profiles[callback.from_user.id] = profile_data
    user_current_photo_index[callback.from_user.id] = 0
    await _render_profile_message(callback, profile_data)


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    telegram_id = callback.from_user.id
    await cache_service.invalidate_user_search_data(telegram_id)
    if telegram_id in user_current_profiles:
        del user_current_profiles[telegram_id]
    if telegram_id in user_current_photo_index:
        del user_current_photo_index[telegram_id]
    
    await safe_edit_message(callback, "🏠 Главное меню:\n\nВыбери действие:", get_start_keyboard())
    await callback.answer()


@router.callback_query(F.data == "my_profile")
async def my_profile(callback: CallbackQuery, session: AsyncSession):
    """Просмотр своей анкеты с кнопкой редактирования"""
    telegram_id = callback.from_user.id
    
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
    
    rating_result = await session.execute(
        select(Rating).where(Rating.user_id == user.id)
    )
    rating = rating_result.scalar_one_or_none()
    
    bio_text = profile.bio if profile.bio else "Не указано"
    rating_text = f"⭐ Рейтинг: {rating.total_score:.1f}" if rating else "⭐ Рейтинг: 0"
    photo_text = "✅ Есть" if profile.photos_count > 0 else "❌ Нет"
    
    search_text = {
        "male": "парней 👨",
        "female": "девушек 👩",
        "all": "всех 👥"
    }.get(profile.search_gender, "всех")
    
    text = (
        f"👤 <b>Твоя анкета</b>\n\n"
        f"📝 Имя: {profile.name}\n"
        f"🎂 Возраст: {profile.age}\n"
        f"👤 Пол: {'👨 Парень' if profile.gender == 'male' else '👩 Девушка'}\n"
        f"📍 Город: {profile.city or 'Не указан'}\n"
        f"📖 О себе: {bio_text}\n"
        f"{rating_text}\n"
        f"📸 Фото: {photo_text}\n"
        f"🎯 Ищу: {search_text}\n\n"
        f"👇 Нажми на кнопку ниже, чтобы редактировать анкету"
    )
    
    photo_ids = await _get_profile_photo_ids(session, user.id, profile.photo_id)
    if photo_ids:
        media = InputMediaPhoto(media=photo_ids[0], caption=text, parse_mode="HTML")
        try:
            await callback.message.edit_media(media=media, reply_markup=get_profile_keyboard())
        except Exception:
            await callback.message.answer_photo(
                photo=photo_ids[0],
                caption=text,
                reply_markup=get_profile_keyboard(),
                parse_mode="HTML"
            )
    else:
        await safe_edit_message(callback, text, get_profile_keyboard(), "HTML")
    await callback.answer()


@router.callback_query(F.data == "search")
async def search(callback: CallbackQuery, session: AsyncSession):
    """Поиск пары с ранжированием и кэшированием"""
    logger.info(f"Поиск пары для пользователя {callback.from_user.id}")
    
    telegram_id = callback.from_user.id
    
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
    
    next_profile = await cache_service.pop_from_search_queue(telegram_id)
    if next_profile:
        await show_profile(callback, next_profile)
        await callback.answer()
        return

    ranked_profiles = await ranking_service.get_ranked_profiles(
        session, user.id, user_profile, telegram_id
    )
    
    logger.info(f"Найдено ранжированных анкет: {len(ranked_profiles)}")
    
    if not ranked_profiles:
        await safe_edit_message(
            callback,
            "😔 К сожалению, пока нет подходящих анкет.\n\n"
            "Попробуй позже или измени параметры поиска!\n"
            "А пока можешь заполнить свою анкету подробнее - это повысит твой рейтинг!",
            get_back_keyboard()
        )
        await callback.answer()
        return
    
    if len(ranked_profiles) > 1:
        await cache_service.set_search_queue(telegram_id, ranked_profiles[1:])

    first_profile = ranked_profiles[0]
    await show_profile(callback, first_profile)


@router.callback_query(F.data.in_(["photo_prev", "photo_next", "photo_info"]))
async def switch_profile_photo(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    profile_data = user_current_profiles.get(telegram_id)
    if not profile_data:
        await callback.answer("Сначала открой анкету через поиск", show_alert=True)
        return

    photo_ids = profile_data.get("photo_ids") or []
    if not photo_ids:
        await callback.answer("У анкеты нет фото", show_alert=True)
        return

    current_idx = user_current_photo_index.get(telegram_id, 0)
    if callback.data == "photo_prev":
        current_idx = (current_idx - 1) % len(photo_ids)
    elif callback.data == "photo_next":
        current_idx = (current_idx + 1) % len(photo_ids)
    user_current_photo_index[telegram_id] = current_idx

    await _render_profile_message(callback, profile_data)
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
        await callback.answer("Ошибка! Попробуй снова /menu")
        return
    
    target_profile = user_current_profiles.get(telegram_id)
    if not target_profile:
        await callback.answer("Сначала открой анкету через поиск", show_alert=True)
        return
    
    target_user_id = target_profile["user_id"]
    if target_user_id == current_user.id:
        await callback.answer("Нельзя лайкнуть самого себя")
        return
    
    existing_like = await session.execute(
        select(Like).where(
            and_(
                Like.from_user_id == current_user.id,
                Like.to_user_id == target_user_id
            )
        )
    )
    is_new_like = existing_like.scalar_one_or_none() is None
    is_new_match = False
    if is_new_like:
        session.add(Like(from_user_id=current_user.id, to_user_id=target_user_id))

    target_user_result = await session.execute(select(User).where(User.id == target_user_id))
    target_user = target_user_result.scalar_one_or_none()

    reverse_like = await session.execute(
        select(Like).where(
            and_(
                Like.from_user_id == target_user_id,
                Like.to_user_id == current_user.id
            )
        )
    )
    if reverse_like.scalar_one_or_none():
        existing_match = await session.execute(
            select(Match).where(
                and_(
                    ((Match.user1_id == current_user.id) & (Match.user2_id == target_user_id)) |
                    ((Match.user1_id == target_user_id) & (Match.user2_id == current_user.id))
                )
            )
        )
        is_new_match = existing_match.scalar_one_or_none() is None
        if is_new_match:
            user1, user2 = sorted([current_user.id, target_user_id])
            session.add(Match(user1_id=user1, user2_id=user2))
            # Отправляем уведомления о мэтче обоим пользователям
            current_profile_result = await session.execute(select(Profile).where(Profile.user_id == current_user.id))
            target_profile_result = await session.execute(select(Profile).where(Profile.user_id == target_user_id))
            current_profile = current_profile_result.scalar_one_or_none()
            target_profile = target_profile_result.scalar_one_or_none()

            if current_profile and target_profile and target_user:
                match_notifications = [
                    (current_user.telegram_id, target_user.telegram_id, target_profile.name),
                    (target_user.telegram_id, current_user.telegram_id, current_profile.name),
                ]
                for recipient_id, partner_id, partner_name in match_notifications:
                    try:
                        await _send_match_notification(
                            callback.bot, recipient_id, partner_id, partner_name
                        )
                    except Exception as e:
                        logger.error(
                            "Не удалось отправить уведомление о мэтче пользователю %s: %s",
                            recipient_id,
                            e,
                        )

    await session.commit()

    if is_new_like and target_user:
        publish_like_event(
            from_user_id=current_user.id,
            to_user_id=target_user_id,
            from_telegram_id=current_user.telegram_id,
            to_telegram_id=target_user.telegram_id,
        )

    if is_new_match and target_user:
        user1, user2 = sorted([current_user.id, target_user_id])
        if current_user.id == user1:
            tg1, tg2 = current_user.telegram_id, target_user.telegram_id
        else:
            tg1, tg2 = target_user.telegram_id, current_user.telegram_id
        publish_match_event(
            user1_id=user1,
            user2_id=user2,
            user1_telegram_id=tg1,
            user2_telegram_id=tg2,
        )

    await callback.answer("❤️ Лайк сохранен!")
    await search(callback, session)


@router.callback_query(F.data == "skip")
async def skip_profile(callback: CallbackQuery, session: AsyncSession):
    """Пропустить анкету"""
    logger.info(f"Пропуск от пользователя {callback.from_user.id}")
    
    await callback.answer("👎 Пропущено")
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
        await safe_edit_message(
            callback,
            "❤️ <b>Твои лайки</b>\n\nТы ещё никому не поставил лайк. Начни поиск пары!",
            get_back_keyboard(),
            "HTML"
        )
        await callback.answer()
        return
    
    likes_text = "❤️ <b>Твои лайки</b>\n\n"
    for like, profile in likes:
        likes_text += f"• {profile.name}, {profile.age} лет\n"
    
    await safe_edit_message(callback, likes_text, get_back_keyboard(), "HTML")
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
        await safe_edit_message(
            callback,
            "💕 <b>Твои мэтчи</b>\n\nУ тебя пока нет мэтчей. Продолжай лайкать анкеты!",
            get_back_keyboard(),
            "HTML"
        )
        await callback.answer()
        return
    
    matches_text = "💕 <b>Твои мэтчи</b>\n\n"
    for match, profile in matches:
        matches_text += f"• {profile.name}, {profile.age} лет\n"
    
    await safe_edit_message(callback, matches_text, get_back_keyboard(), "HTML")
    await callback.answer()


# ========== РЕДАКТИРОВАНИЕ ПРОФИЛЯ ==========

@router.callback_query(F.data == "edit_profile")
async def edit_profile(callback: CallbackQuery, session: AsyncSession):
    """Меню редактирования профиля"""
    telegram_id = callback.from_user.id
    
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
    
    search_text = {
        "male": "парней 👨",
        "female": "девушек 👩",
        "all": "всех 👥"
    }.get(profile.search_gender, "всех")
    
    text = (
        "✏️ <b>Редактирование профиля</b>\n\n"
        f"Текущие данные:\n"
        f"• Имя: {profile.name}\n"
        f"• Возраст: {profile.age}\n"
        f"• Пол: {'Парень' if profile.gender == 'male' else 'Девушка'}\n"
        f"• Город: {profile.city or 'Не указан'}\n"
        f"• Описание: {profile.bio[:50] + '...' if profile.bio and len(profile.bio) > 50 else profile.bio or 'Не указано'}\n"
        f"• Ищу: {search_text}\n\n"
        f"Выбери, что хочешь изменить:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Изменить город", callback_data="edit_city")],
        [InlineKeyboardButton(text="📖 Изменить описание", callback_data="edit_bio")],
        [InlineKeyboardButton(text="📸 Изменить фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="🎯 Кого ищу", callback_data="edit_search_gender")],
        [InlineKeyboardButton(text="🔄 Создать анкету заново", callback_data="reset_profile")],
        [InlineKeyboardButton(text="⬅️ Назад к анкете", callback_data="my_profile")]
    ])
    
    await safe_edit_message(callback, text, keyboard, "HTML")
    await callback.answer()


@router.callback_query(F.data == "edit_city")
async def edit_city(callback: CallbackQuery, state: FSMContext):
    """Изменить город"""
    await callback.message.answer("Введи новый город:")
    await state.set_state(EditProfileForm.city)
    await callback.answer()


@router.message(EditProfileForm.city)
async def update_city(message: Message, state: FSMContext, session: AsyncSession):
    """Обновить город"""
    city = message.text.strip()
    
    if len(city) < 2 or len(city) > 100:
        await message.answer("Название города должно быть от 2 до 100 символов!")
        return
    
    telegram_id = message.from_user.id
    
    result = await session.execute(
        select(Profile)
        .join(User)
        .where(User.telegram_id == telegram_id)
    )
    profile = result.scalar_one_or_none()
    
    if profile:
        profile.city = city
        await session.commit()
        await cache_service.invalidate_user_search_data(telegram_id)
        await message.answer(f"✅ Город успешно изменён на {city}!")
    else:
        await message.answer("❌ Профиль не найден!")
    
    await state.clear()
    await message.answer("Вернуться в меню: /menu")


@router.callback_query(F.data == "edit_bio")
async def edit_bio(callback: CallbackQuery, state: FSMContext):
    """Изменить описание"""
    await callback.message.answer(
        "Введи новое описание (до 500 символов)\n"
        "Или напиши 'пропустить', чтобы удалить описание:"
    )
    await state.set_state(EditProfileForm.bio)
    await callback.answer()


@router.message(EditProfileForm.bio)
async def update_bio(message: Message, state: FSMContext, session: AsyncSession):
    """Обновить описание"""
    bio = message.text.strip()
    
    if bio.lower() in ["пропустить", "нет", "-", "skip"]:
        bio = None
    
    if bio and len(bio) > 500:
        await message.answer("Описание не должно превышать 500 символов!")
        return
    
    telegram_id = message.from_user.id
    
    result = await session.execute(
        select(Profile)
        .join(User)
        .where(User.telegram_id == telegram_id)
    )
    profile = result.scalar_one_or_none()
    
    if profile:
        profile.bio = bio
        await session.commit()
        await cache_service.invalidate_user_search_data(telegram_id)
        await message.answer("✅ Описание успешно изменено!")
    else:
        await message.answer("❌ Профиль не найден!")
    
    await state.clear()
    await message.answer("Вернуться в меню: /menu")


@router.callback_query(F.data == "edit_photo")
async def edit_photo(callback: CallbackQuery, state: FSMContext):
    """Изменить фото"""
    await state.update_data(photo_ids=[])
    await callback.message.answer("Пожалуйста, отправьте фото (можно до 3) 📸")
    await state.set_state(EditProfileForm.photo)
    await callback.answer()


@router.message(EditProfileForm.photo, F.photo)
async def update_photo(message: Message, state: FSMContext, session: AsyncSession):
    """Обновить фото"""
    photo = message.photo[-1]
    file_id = photo.file_id

    data = await state.get_data()
    photo_ids = list(data.get("photo_ids", []))
    if len(photo_ids) >= 3:
        await message.answer("Можно добавить максимум 3 фото.")
        return

    photo_ids.append(file_id)
    await state.update_data(photo_ids=photo_ids)

    if len(photo_ids) < 3:
        await message.answer(
            f"Фото {len(photo_ids)}/3 добавлено. Это все или можете добавить еще фото.",
            reply_markup=get_photo_done_keyboard()
        )
        return

    await _save_edited_photos(message, state, session, photo_ids)


@router.callback_query(EditProfileForm.photo, F.data == "photo_done")
async def update_photo_done(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    photo_ids = list(data.get("photo_ids", []))
    if not photo_ids:
        await callback.answer("Нужно добавить хотя бы одно фото.", show_alert=True)
        return
    await callback.answer()
    await _save_edited_photos(callback.message, state, session, photo_ids)


async def _save_edited_photos(message: Message, state: FSMContext, session: AsyncSession, photo_ids: list[str]):
    telegram_id = message.from_user.id
    
    result = await session.execute(
        select(Profile)
        .join(User)
        .where(User.telegram_id == telegram_id)
    )
    profile = result.scalar_one_or_none()
    
    if profile:
        profile.photo_id = photo_ids[0]
        profile.photos_count = len(photo_ids)
        await session.execute(delete(ProfilePhoto).where(ProfilePhoto.profile_id == profile.id))
        for idx, photo_id in enumerate(photo_ids, start=1):
            session.add(ProfilePhoto(profile_id=profile.id, file_id=photo_id, position=idx))
        await session.commit()
        await cache_service.invalidate_user_search_data(telegram_id)
        await message.answer(f"✅ Фото успешно обновлены ({len(photo_ids)}/3)!")
    else:
        await message.answer("❌ Профиль не найден!")
    
    await state.clear()
    await message.answer("Вернуться в меню: /menu")


@router.message(EditProfileForm.photo)
async def edit_photo_invalid(message: Message, state: FSMContext):
    """Если прислали не фото"""
    await message.answer("Пожалуйста, отправьте фото (можно до 3) 📸")


@router.callback_query(F.data == "edit_search_gender")
async def edit_search_gender(callback: CallbackQuery, session: AsyncSession):
    """Изменить кого ищет пользователь"""
    telegram_id = callback.from_user.id
    
    result = await session.execute(
        select(Profile)
        .join(User)
        .where(User.telegram_id == telegram_id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        await callback.answer("Профиль не найден!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Парней", callback_data="set_search_male")],
        [InlineKeyboardButton(text="👩 Девушек", callback_data="set_search_female")],
        [InlineKeyboardButton(text="👥 Всех", callback_data="set_search_all")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="edit_profile")]
    ])
    
    await safe_edit_message(
        callback,
        "🎯 <b>Кого ты хочешь искать?</b>\n\nВыбери предпочтения:",
        keyboard,
        "HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_search_"))
async def set_search_gender(callback: CallbackQuery, session: AsyncSession):
    """Установить кого искать"""
    choice = callback.data.split("_")[2]  # male, female, all
    
    telegram_id = callback.from_user.id
    
    result = await session.execute(
        select(Profile)
        .join(User)
        .where(User.telegram_id == telegram_id)
    )
    profile = result.scalar_one_or_none()
    
    if profile:
        profile.search_gender = choice
        await session.commit()
        await cache_service.invalidate_user_search_data(telegram_id)

        search_text = {
            "male": "парней 👨",
            "female": "девушек 👩",
            "all": "всех 👥"
        }.get(choice, "всех")
        
        await callback.message.answer(f"✅ Теперь ты ищешь {search_text}!")
    else:
        await callback.message.answer("❌ Профиль не найден!")
    
    await callback.message.answer("Вернуться в меню: /menu")


@router.callback_query(F.data == "reset_profile")
async def reset_profile_confirm(callback: CallbackQuery):
    """Подтверждение сброса профиля"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить и создать новую", callback_data="reset_confirm")],
        [InlineKeyboardButton(text="❌ Нет, отмена", callback_data="edit_profile")]
    ])
    
    text = (
        "⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        "При создании новой анкеты:\n"
        "• Все твои лайки и мэтчи будут удалены\n"
        "• Твой рейтинг обнулится\n"
        "• Другие пользователи потеряют свои лайки к тебе\n\n"
        "Ты уверен(а), что хочешь создать анкету заново?"
    )
    
    await safe_edit_message(callback, text, keyboard, "HTML")
    await callback.answer()


@router.callback_query(F.data == "reset_confirm")
async def reset_profile(callback: CallbackQuery, session: AsyncSession):
    """Сбросить профиль"""
    telegram_id = callback.from_user.id
    
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("Профиль не найден!")
        return
    
    await session.execute(delete(Like).where(Like.from_user_id == user.id))
    await session.execute(delete(Like).where(Like.to_user_id == user.id))
    await session.execute(delete(Match).where(Match.user1_id == user.id))
    await session.execute(delete(Match).where(Match.user2_id == user.id))
    await session.execute(delete(Rating).where(Rating.user_id == user.id))
    await session.execute(delete(Profile).where(Profile.user_id == user.id))
    await session.execute(delete(User).where(User.id == user.id))
    
    await session.commit()
    await cache_service.invalidate_user_search_data(telegram_id)

    await callback.message.answer(
        "🔄 Твоя анкета удалена!\n\n"
        "Давай создадим новую. Напиши /start"
    )
    await callback.answer()