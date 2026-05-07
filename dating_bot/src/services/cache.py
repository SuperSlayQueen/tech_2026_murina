import json
import logging
from typing import Optional, List, Dict
import redis.asyncio as redis
from src.config.settings import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Сервис для кэширования анкет в Redis"""
    
    def __init__(self):
        self.redis_client = None
    
    async def _get_client(self):
        """Получить или создать клиент Redis"""
        if self.redis_client is None:
            self.redis_client = await redis.from_url(
                f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
                decode_responses=True
            )
        return self.redis_client
    
    async def cache_profiles(self, user_telegram_id: int, profiles: List[Dict]) -> bool:
        """Кэшировать список анкет для пользователя"""
        try:
            client = await self._get_client()
            key = f"profiles_cache:{user_telegram_id}"
            
            profiles_json = json.dumps(profiles, default=str)
            await client.setex(key, 3600, profiles_json)  # TTL 1 час
            
            logger.info(f"Cached {len(profiles)} profiles for user {user_telegram_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cache profiles: {e}")
            return False
    
    async def get_cached_profiles(self, user_telegram_id: int) -> Optional[List[Dict]]:
        """Получить кэшированные анкеты для пользователя"""
        try:
            client = await self._get_client()
            key = f"profiles_cache:{user_telegram_id}"
            
            cached = await client.get(key)
            if cached:
                profiles = json.loads(cached)
                logger.info(f"Got {len(profiles)} cached profiles for user {user_telegram_id}")
                return profiles
            return None
        except Exception as e:
            logger.error(f"Failed to get cached profiles: {e}")
            return None
    
    async def update_cache(self, user_telegram_id: int, profiles: List[Dict]) -> bool:
        """Обновить кэш (удалить первую анкету)"""
        if not profiles:
            await self.clear_cache(user_telegram_id)
            return True
        
        return await self.cache_profiles(user_telegram_id, profiles)
    
    async def clear_cache(self, user_telegram_id: int) -> bool:
        """Очистить кэш для пользователя"""
        try:
            client = await self._get_client()
            key = f"profiles_cache:{user_telegram_id}"
            await client.delete(key)
            logger.info(f"Cleared cache for user {user_telegram_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False
    
    async def close(self):
        """Закрыть соединение с Redis"""
        if self.redis_client:
            await self.redis_client.close()