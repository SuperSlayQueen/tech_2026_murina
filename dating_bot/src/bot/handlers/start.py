import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from src.backend.models import User, Profile, ProfilePhoto, Rating, Like, Match
from src.bot.keyboards import get_start_keyboard, get_back_keyboard, get_photo_done_keyboard

logger = logging.getLogger(__name__)
router = Router()


class ProfileForm(StatesGroup):
    """Состояния для заполнения анкеты"""
    name = State()
    age = State()
    gender = State()
    city = State()
    bio = State()
    photo = State()
    search_gender = State()  # Новое состояние


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды /start"""
    telegram_id = message.from_user.id
    
    result = await session.execute(
        select(User, Profile)
        .join(Profile, User.id == Profile.user_id)
        .where(User.telegram_id == telegram_id)
    )
    row = result.first()
    
    if row:
        user, profile = row
        await message.answer(
            f"Привет, {profile.name}! 👋\n\n"
            f"Я снова рад тебя видеть! Что будем делать?",
            reply_markup=get_start_keyboard()
        )
        await state.clear()
    else:
        await message.answer(
            "Привет! 👋\n\n"
            "Добро пожаловать в Dating Bot!\n\n"
            "Давай начнём! Как тебя зовут?"
        )
        await state.set_state(ProfileForm.name)


@router.message((F.text == "/menu") | (F.text.casefold() == "menu"))
async def cmd_menu(message: Message, state: FSMContext, session: AsyncSession):
    """Показать главное меню"""
    telegram_id = message.from_user.id
    result = await session.execute(
        select(User, Profile)
        .join(Profile, User.id == Profile.user_id)
        .where(User.telegram_id == telegram_id)
    )
    row = result.first()

    if row:
        user, profile = row
        await message.answer(
            f"Главное меню, {profile.name} 👋",
            reply_markup=get_start_keyboard()
        )
        await state.clear()
    else:
        await message.answer("Сначала создай анкету через /start")


@router.message(ProfileForm.name)
async def process_name(message: Message, state: FSMContext):
    """Обработка имени"""
    name = message.text.strip()
    
    if len(name) < 2 or len(name) > 50:
        await message.answer("Имя должно быть от 2 до 50 символов. Попробуй ещё раз:")
        return
    
    await state.update_data(name=name)
    await message.answer(f"Приятно познакомиться, {name}! 😊\n\nСколько тебе лет?")
    await state.set_state(ProfileForm.age)


@router.message(ProfileForm.age)
async def process_age(message: Message, state: FSMContext):
    """Обработка возраста"""
    try:
        age = int(message.text.strip())
        
        if age < 16 or age > 100:
            await message.answer("Возраст должен быть от 16 до 100 лет. Попробуй ещё раз:")
            return
        
        await state.update_data(age=age)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👨 Парень", callback_data="gender_male")],
            [InlineKeyboardButton(text="👩 Девушка", callback_data="gender_female")]
        ])
        await message.answer("Кто ты?", reply_markup=keyboard)
        await state.set_state(ProfileForm.gender)
    except ValueError:
        await message.answer("Пожалуйста, введи число (возраст):")


@router.callback_query(ProfileForm.gender, F.data.in_(["gender_male", "gender_female"]))
async def process_gender(callback: CallbackQuery, state: FSMContext):
    """Обработка пола через кнопки"""
    gender = "male" if callback.data == "gender_male" else "female"
    await state.update_data(gender=gender)
    await callback.message.answer("Из какого ты города?")
    await state.set_state(ProfileForm.city)
    await callback.answer()


@router.message(ProfileForm.gender)
async def process_gender_invalid(message: Message):
    await message.answer("Пожалуйста, выбери пол кнопкой.")


@router.message(ProfileForm.city)
async def process_city(message: Message, state: FSMContext):
    """Обработка города"""
    city = message.text.strip()
    
    if len(city) < 2 or len(city) > 100:
        await message.answer("Название города должно быть от 2 до 100 символов. Попробуй ещё раз:")
        return
    
    await state.update_data(city=city)
    await message.answer(
        "Расскажи немного о себе (хобби, интересы, что ищешь).\n\n"
        "Можно написать 'пропустить', если не хочешь заполнять:"
    )
    await state.set_state(ProfileForm.bio)


@router.message(ProfileForm.bio)
async def process_bio(message: Message, state: FSMContext):
    """Обработка описания"""
    bio = message.text.strip()
    
    if bio.lower() in ["пропустить", "нет", "-", "skip"]:
        bio = None
    
    await state.update_data(bio=bio)
    await message.answer(
        "Пожалуйста, отправьте фото (можно до 3) 📸"
    )
    await state.set_state(ProfileForm.photo)


@router.message(ProfileForm.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Обработка фото"""
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

    # 3 фото уже набрано, переходим к выбору предпочтений
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Парней", callback_data="search_male")],
        [InlineKeyboardButton(text="👩 Девушек", callback_data="search_female")],
        [InlineKeyboardButton(text="👥 Всех", callback_data="search_all")]
    ])
    
    await message.answer(
        "👥 <b>Кого ты хочешь искать?</b>\n\n"
        "Выбери предпочтения:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(ProfileForm.search_gender)


@router.callback_query(ProfileForm.photo, F.data == "photo_done")
async def process_photo_done(callback: CallbackQuery, state: FSMContext):
    """Завершение загрузки фото"""
    data = await state.get_data()
    photo_ids = list(data.get("photo_ids", []))
    if not photo_ids:
        await callback.answer("Сначала добавь хотя бы одно фото.", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Парней", callback_data="search_male")],
        [InlineKeyboardButton(text="👩 Девушек", callback_data="search_female")],
        [InlineKeyboardButton(text="👥 Всех", callback_data="search_all")]
    ])

    await callback.message.answer(
        "👥 <b>Кого ты хочешь искать?</b>\n\n"
        "Выбери предпочтения:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(ProfileForm.search_gender)
    await callback.answer()


@router.message(ProfileForm.photo)
async def process_photo_invalid(message: Message, state: FSMContext):
    """Если прислали не фото"""
    await message.answer("Пожалуйста, отправьте фото (можно до 3) 📸")


@router.callback_query(ProfileForm.search_gender, F.data.startswith("search_"))
async def process_search_gender(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка выбора кого искать и завершение регистрации"""
    choice = callback.data.split("_")[1]  # male, female, all
    
    search_gender_map = {
        "male": "male",
        "female": "female",
        "all": "all"
    }
    search_gender = search_gender_map.get(choice, "all")
    
    # Получаем все данные из состояния
    data = await state.get_data()
    telegram_id = callback.from_user.id
    
    # Создаём пользователя
    user = User(telegram_id=telegram_id)
    session.add(user)
    await session.flush()
    
    # Создаём профиль
    profile = Profile(
        user_id=user.id,
        name=data["name"],
        age=data["age"],
        gender=data["gender"],
        search_gender=search_gender,
        city=data["city"],
        bio=data.get("bio"),
        photo_id=(data.get("photo_ids") or [None])[0],
        photos_count=len(data.get("photo_ids") or [])
    )
    session.add(profile)
    await session.flush()

    for idx, photo_id in enumerate(data.get("photo_ids") or [], start=1):
        session.add(ProfilePhoto(profile_id=profile.id, file_id=photo_id, position=idx))
    
    # Создаём начальный рейтинг
    rating = Rating(
        user_id=user.id,
        primary_score=0.0,
        behavior_score=0.0,
        total_score=0.0
    )
    session.add(rating)
    
    await session.commit()
    
    logger.info(f"Зарегистрирован новый пользователь: {telegram_id}")
    
    search_text = {
        "male": "парней 👨",
        "female": "девушек 👩",
        "all": "всех 👥"
    }.get(search_gender, "всех")
    
    await callback.message.edit_text(
        f"🎉 Отлично! Твоя анкета готова!\n\n"
        f"📝 Имя: {data['name']}\n"
        f"🎂 Возраст: {data['age']}\n"
        f"📍 Город: {data['city']}\n"
        f"👥 Ищу: {search_text}\n"
        f"📸 Фото: добавлено\n\n"
        f"Теперь ты можешь искать свою пару!",
        reply_markup=get_start_keyboard()
    )
    await state.clear()
    await callback.answer()