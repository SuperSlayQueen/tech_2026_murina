import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from src.backend.models import Profile, ProfilePhoto, User, Like, Rating
from src.services.cache import CacheService

logger = logging.getLogger(__name__)


class RankingService:
    """Сервис для ранжирования анкет"""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
    
    async def get_ranked_profiles(
        self,
        session: AsyncSession,
        user_id: int,
        user_profile: Profile,
        telegram_id: int,
    ) -> list:
        """
        Получить ранжированный список анкет для пользователя.
        Сначала Redis-кэш, при промахе — запрос в БД и сохранение в Redis.
        """
        cached = await self.cache_service.get_cached_profiles(telegram_id)
        if cached is not None:
            logger.info(f"Ранжирование из Redis для telegram_id={telegram_id}: {len(cached)} анкет")
            return cached

        logger.info(f"Ранжирование для пользователя {user_id}, пол={user_profile.gender}, ищет={user_profile.search_gender}")
        
        # Получаем ID пользователей, которых уже лайкнули
        liked_users = await session.execute(
            select(Like.to_user_id).where(Like.from_user_id == user_id)
        )
        liked_ids = [row[0] for row in liked_users.all()]
        logger.info(f"Уже лайкнутые ID: {liked_ids}")
        
        # Определяем, кого искать на основе search_gender пользователя
        search_gender = user_profile.search_gender
        
        # Базовый запрос - исключаем себя и уже лайкнутых
        query = select(Profile, Rating).join(
            Rating, Profile.user_id == Rating.user_id
        ).where(
            and_(
                Profile.user_id != user_id,
                Profile.user_id.notin_(liked_ids) if liked_ids else True
            )
        )
        
        # Фильтруем по полу, если не выбран "all"
        if search_gender == 'male':
            query = query.where(Profile.gender == 'male')
            logger.info("Фильтр: показываем только парней")
        elif search_gender == 'female':
            query = query.where(Profile.gender == 'female')
            logger.info("Фильтр: показываем только девушек")
        else:  # search_gender == 'all'
            logger.info("Фильтр: показываем всех")
        
        results = await session.execute(query)
        profiles_with_ratings = results.all()
        
        logger.info(f"Найдено профилей после фильтрации: {len(profiles_with_ratings)}")
        
        ranked = []
        for profile, rating in profiles_with_ratings:
            photos_result = await session.execute(
                select(ProfilePhoto.file_id)
                .where(ProfilePhoto.profile_id == profile.id)
                .order_by(ProfilePhoto.position.asc())
            )
            photo_ids = [row[0] for row in photos_result.all()]
            if not photo_ids and profile.photo_id:
                photo_ids = [profile.photo_id]

            # Уровень 1: Первичный рейтинг (возраст, город, полнота анкеты)
            primary_score = await self._calculate_primary_score(user_profile, profile)
            
            # Уровень 2: Поведенческий рейтинг (лайки, мэтчи)
            behavior_score = rating.behavior_score if rating else 0
            
            # Уровень 3: Комбинированный рейтинг
            total_score = primary_score * 0.6 + behavior_score * 0.4
            
            ranked.append({
                'user_id': profile.user_id,
                'name': profile.name,
                'age': profile.age,
                'gender': profile.gender,
                'city': profile.city,
                'bio': profile.bio,
                'photo_ids': photo_ids,
                'rating': total_score,
                'primary_score': primary_score,
                'behavior_score': behavior_score
            })
        
        # Сортируем по комбинированному рейтингу (по убыванию)
        ranked.sort(key=lambda x: x['rating'], reverse=True)
        
        logger.info(f"Отранжировано анкет: {len(ranked)}")
        if ranked:
            logger.info(f"Топ-1: {ranked[0]['name']} с рейтингом {ranked[0]['rating']:.2f}")

        await self.cache_service.cache_profiles(telegram_id, ranked)
        return ranked
    
    async def _calculate_primary_score(self, user_profile: Profile, target_profile: Profile) -> float:
        """
        Уровень 1: Первичный рейтинг на основе данных анкеты
        Максимум 3 балла
        """
        score = 0.0
        
        # 1. Возраст (чем ближе к возрасту пользователя, тем выше балл)
        # до 1 балла
        age_diff = abs(user_profile.age - target_profile.age)
        if age_diff <= 3:
            score += 1.0
        elif age_diff <= 5:
            score += 0.7
        elif age_diff <= 10:
            score += 0.4
        else:
            score += 0.1
        
        # 2. Город (совпадение городов дает бонус)
        # до 0.8 балла
        if user_profile.city and target_profile.city:
            if user_profile.city.lower() == target_profile.city.lower():
                score += 0.8
        
        # 3. Полнота анкеты (наличие био и фото)
        # до 1 балла
        completeness = 0
        if target_profile.bio:
            completeness += 0.5
        if target_profile.photos_count > 0:
            completeness += 0.5
        
        score += completeness
        
        return min(score, 3.0)  # Максимум 3 балла за первичный рейтинг