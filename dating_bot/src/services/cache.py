import json
import logging
from typing import Optional, List, Dict
import redis.asyncio as redis
from src.config.settings import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Сервис для кэширования анкет и очереди поиска в Redis"""

    PROFILES_KEY = "profiles_cache:{telegram_id}"
    SEARCH_QUEUE_KEY = "search_queue:{telegram_id}"
    CACHE_TTL = 3600

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
        """Кэшировать отранжированный список анкет для пользователя"""
        try:
            client = await self._get_client()
            key = self.PROFILES_KEY.format(telegram_id=user_telegram_id)

            profiles_json = json.dumps(profiles, default=str)
            await client.setex(key, self.CACHE_TTL, profiles_json)
            
            logger.info(f"Cached {len(profiles)} profiles for user {user_telegram_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cache profiles: {e}")
            return False
    
    async def get_cached_profiles(self, user_telegram_id: int) -> Optional[List[Dict]]:
        """Получить кэшированный отранжированный список анкет"""
        try:
            client = await self._get_client()
            key = self.PROFILES_KEY.format(telegram_id=user_telegram_id)
            
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
        """Очистить кэш отранжированных анкет"""
        try:
            client = await self._get_client()
            key = self.PROFILES_KEY.format(telegram_id=user_telegram_id)
            await client.delete(key)
            logger.info(f"Cleared profiles cache for user {user_telegram_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False

    async def set_search_queue(self, user_telegram_id: int, profiles: List[Dict]) -> bool:
        """Сохранить очередь анкет для просмотра при поиске"""
        try:
            client = await self._get_client()
            key = self.SEARCH_QUEUE_KEY.format(telegram_id=user_telegram_id)
            await client.setex(key, self.CACHE_TTL, json.dumps(profiles, default=str))
            logger.info(f"Search queue set for {user_telegram_id}: {len(profiles)} profiles")
            return True
        except Exception as e:
            logger.error(f"Failed to set search queue: {e}")
            return False

    async def pop_from_search_queue(self, user_telegram_id: int) -> Optional[Dict]:
        """Взять следующую анкету из очереди поиска"""
        try:
            client = await self._get_client()
            key = self.SEARCH_QUEUE_KEY.format(telegram_id=user_telegram_id)
            raw = await client.get(key)
            if not raw:
                return None

            queue = json.loads(raw)
            if not queue:
                await client.delete(key)
                return None

            next_profile = queue.pop(0)
            if queue:
                await client.setex(key, self.CACHE_TTL, json.dumps(queue, default=str))
            else:
                await client.delete(key)

            return next_profile
        except Exception as e:
            logger.error(f"Failed to pop from search queue: {e}")
            return None

    async def clear_search_queue(self, user_telegram_id: int) -> bool:
        """Очистить очередь поиска"""
        try:
            client = await self._get_client()
            key = self.SEARCH_QUEUE_KEY.format(telegram_id=user_telegram_id)
            await client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to clear search queue: {e}")
            return False

    async def invalidate_user_search_data(self, user_telegram_id: int) -> None:
        """Сбросить кэш и очередь поиска пользователя"""
        await self.clear_cache(user_telegram_id)
        await self.clear_search_queue(user_telegram_id)

    async def invalidate_all_profile_caches(self) -> int:
        """Сбросить все кэши анкет (после массового пересчёта рейтингов)"""
        try:
            client = await self._get_client()
            deleted = 0
            async for key in client.scan_iter(match="profiles_cache:*"):
                await client.delete(key)
                deleted += 1
            logger.info(f"Invalidated {deleted} profile caches")
            return deleted
        except Exception as e:
            logger.error(f"Failed to invalidate all caches: {e}")
            return 0

    async def close(self):
        """Закрыть соединение с Redis"""
        if self.redis_client:
            await self.redis_client.close()