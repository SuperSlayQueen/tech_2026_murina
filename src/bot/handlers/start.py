import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.backend.models import User, Profile
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
    
    # Проверяем, есть ли пользователь в БД
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if user:
        # Пользователь уже зарегистрирован
        await message.answer(
            f"Привет, {user.profile.name if user.profile else 'друг'}! 👋\n\n"
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
async def process_name(message: Message, state: FSMContext, session: AsyncSession):
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
    age = message.text.strip()
    
    if not age.isdigit():
        await message.answer("Пожалуйста, введи число (возраст):")
        return
    
    age = int(age)
    if age < 16 or age > 100:
        await message.answer("Возраст должен быть от 16 до 100 лет. Попробуй ещё раз:")
        return
    
    await state.update_data(age=age)
    await message.answer("Кто ты?\n\nПарень или девушка?")
    await state.set_state(ProfileForm.gender)


@router.message(ProfileForm.gender)
async def process_gender(message: Message, state: FSMContext):
    """Обработка пола"""
    gender = message.text.strip().lower()
    
    if gender in ["парень", "мужской", "м", "male"]:
        gender = "male"
    elif gender in ["девушка", "женский", "ж", "female"]:
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
    
    if bio.lower() in ["пропустить", "нет", "-"]:
        bio = None
    
    # Получаем все данные из состояния
    data = await state.get_data()
    telegram_id = message.from_user.id
    
    # Создаём пользователя и профиль
    user = User(telegram_id=telegram_id)
    profile = Profile(
        name=data["name"],
        age=data["age"],
        gender=data["gender"],
        city=data["city"],
        bio=bio,
    )
    user.profile = profile
    
    session.add(user)
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
