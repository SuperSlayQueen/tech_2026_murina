import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.backend.models import User, Profile, Rating
from src.bot.keyboards import get_start_keyboard, get_back_keyboard

logger = logging.getLogger(__name__)
router = Router()


class ProfileForm(StatesGroup):
    """Состояния для заполнения анкеты"""
    name = State()
    age = State()
    gender = State()
    city = State()
    bio = State()


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды /start"""
    telegram_id = message.from_user.id
    
    # Явно подгружаем profile через join
    result = await session.execute(
        select(User, Profile)
        .join(Profile, User.id == Profile.user_id)
        .where(User.telegram_id == telegram_id)
    )
    row = result.first()
    
    if row:
        user, profile = row
        # Пользователь уже зарегистрирован
        await message.answer(
            f"Привет, {profile.name}! 👋\n\n"
            f"Я снова рад тебя видеть! Что будем делать?",
            reply_markup=get_start_keyboard()
        )
        await state.clear()
    else:
        # Новый пользователь - начинаем регистрацию
        await message.answer(
            "Привет! 👋\n\n"
            "Добро пожаловать в Dating Bot! Здесь ты сможешь найти свою вторую половинку.\n\n"
            "Давай создадим твою анкету. Как тебя зовут?"
        )
        await state.set_state(ProfileForm.name)


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
        await message.answer("Кто ты?\n\nНапиши 'парень' или 'девушка':")
        await state.set_state(ProfileForm.gender)
    except ValueError:
        await message.answer("Пожалуйста, введи число (возраст):")


@router.message(ProfileForm.gender)
async def process_gender(message: Message, state: FSMContext):
    """Обработка пола"""
    gender_text = message.text.strip().lower()
    
    if gender_text in ["парень", "мужской", "м", "male", "мужчина"]:
        gender = "male"
    elif gender_text in ["девушка", "женский", "ж", "female", "женщина"]:
        gender = "female"
    else:
        await message.answer("Пожалуйста, напиши 'парень' или 'девушка':")
        return
    
    await state.update_data(gender=gender)
    await message.answer("Из какого ты города?")
    await state.set_state(ProfileForm.city)


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
async def process_bio(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка описания и завершение регистрации"""
    bio = message.text.strip()
    
    if bio.lower() in ["пропустить", "нет", "-", "skip"]:
        bio = None
    
    # Получаем все данные из состояния
    data = await state.get_data()
    telegram_id = message.from_user.id
    
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
        city=data["city"],
        bio=bio,
        photos_count=0
    )
    session.add(profile)
    
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
    
    await message.answer(
        f"Отлично! Твоя анкета готова! 🎉\n\n"
        f"Имя: {data['name']}\n"
        f"Возраст: {data['age']}\n"
        f"Город: {data['city']}\n\n"
        f"Теперь ты можешь искать свою пару!",
        reply_markup=get_start_keyboard()
    )
    await state.clear()