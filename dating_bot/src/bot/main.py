import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from src.config.settings import settings
from src.backend.database import init_db, close_db
from src.bot.handlers.start import router as start_router
from src.bot.handlers.menu import router as menu_router
from src.bot.middleware import DatabaseMiddleware
from src.services.cache import CacheService


# Настройка логирования
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    logger.info("Бот запускается...")
    await init_db()
    logger.info("База данных инициализирована")
    
    # Устанавливаем команды меню
    commands = [
        types.BotCommand(command="/start", description="Запустить бота и создать анкету"),
    ]
    await bot.set_my_commands(commands)
    logger.info(f"Бот запущен: @{(await bot.get_me()).username}")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("Бот останавливается...")
    await close_db()
    
    # Закрываем соединение с Redis
    cache_service = CacheService()
    await cache_service.close()
    
    logger.info("Подключения закрыты")


def create_dispatcher() -> Dispatcher:
    """Создание диспетчера с роутерами"""
    dp = Dispatcher(storage=MemoryStorage())
    
    # Добавляем middleware для БД
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    
    # Подключаем роутеры
    dp.include_router(start_router)
    dp.include_router(menu_router)
    
    # Регистрируем хуки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    return dp


async def run_bot():
    """Запуск бота"""
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = create_dispatcher()
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_bot())