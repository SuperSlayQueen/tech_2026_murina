from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.database import async_session_maker
from src.config.settings import settings


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для добавления сессии БД в каждый запрос"""
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        async with async_session_maker() as session:
            data["session"] = session
            return await handler(event, data)


class OwnerOnlyMiddleware(BaseMiddleware):
    """Разрешает доступ к боту только владельцу"""

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        owner_id = settings.owner_telegram_id

        # Если OWNER_TELEGRAM_ID не задан, блокируем доступ всем.
        if owner_id <= 0:
            if isinstance(event, Message):
                await event.answer("⛔ Бот не настроен: владелец не задан.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Доступ запрещен", show_alert=True)
            return None

        user = getattr(event, "from_user", None)
        if user is None or user.id != owner_id:
            if isinstance(event, Message):
                await event.answer("⛔ Доступ запрещен.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Доступ запрещен", show_alert=True)
            return None

        return await handler(event, data)