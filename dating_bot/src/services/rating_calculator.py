import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from src.backend.models import User, Profile, Like, Match, Rating

logger = logging.getLogger(__name__)


class RatingCalculator:
    """Калькулятор поведенческого рейтинга"""
    
    async def update_rating(self, session: AsyncSession, user_id: int):
        """
        Обновить рейтинг пользователя на основе взаимодействий
        """
        # Получаем статистику пользователя
        stats = await self._get_user_stats(session, user_id)
        
        # Рассчитываем поведенческий рейтинг
        behavior_score = self._calculate_behavior_score(stats)
        
        # Обновляем или создаем запись рейтинга
        rating_result = await session.execute(
            select(Rating).where(Rating.user_id == user_id)
        )
        rating = rating_result.scalar_one_or_none()
        
        if rating:
            rating.behavior_score = behavior_score
            rating.total_score = rating.primary_score * 0.6 + behavior_score * 0.4
        else:
            rating = Rating(
                user_id=user_id,
                primary_score=0.0,
                behavior_score=behavior_score,
                total_score=behavior_score
            )
            session.add(rating)
        
        await session.commit()
        logger.info(f"Updated rating for user {user_id}: {behavior_score}")
        
        return rating
    
    async def _get_user_stats(self, session: AsyncSession, user_id: int) -> dict:
        """Получить статистику пользователя"""
        
        # Количество полученных лайков
        likes_received = await session.execute(
            select(func.count(Like.id)).where(Like.to_user_id == user_id)
        )
        likes_count = likes_received.scalar() or 0
        
        # Количество поставленных лайков
        likes_given = await session.execute(
            select(func.count(Like.id)).where(Like.from_user_id == user_id)
        )
        given_count = likes_given.scalar() or 0
        
        # Количество мэтчей
        matches_count = await session.execute(
            select(func.count(Match.id)).where(
                (Match.user1_id == user_id) | (Match.user2_id == user_id)
            )
        )
        matches = matches_count.scalar() or 0
        
        # Соотношение лайков к пропускам (для простоты берем лайки/просмотры)
        view_count = given_count + 10  # Примерное количество просмотров
        
        return {
            'likes_received': likes_count,
            'likes_given': given_count,
            'matches': matches,
            'like_ratio': given_count / max(view_count, 1)
        }
    
    def _calculate_behavior_score(self, stats: dict) -> float:
        """
        Уровень 2: Поведенческий рейтинг
        """
        score = 0.0
        
        # 1. Количество лайков анкеты (до 2 баллов)
        if stats['likes_received'] >= 20:
            score += 2.0
        elif stats['likes_received'] >= 10:
            score += 1.5
        elif stats['likes_received'] >= 5:
            score += 1.0
        elif stats['likes_received'] >= 1:
            score += 0.5
        
        # 2. Соотношение лайков и пропусков (до 1 балла)
        if stats['like_ratio'] >= 0.7:
            score += 1.0
        elif stats['like_ratio'] >= 0.5:
            score += 0.7
        elif stats['like_ratio'] >= 0.3:
            score += 0.4
        
        # 3. Частота взаимных лайков (мэтчей) - до 1 балла
        if stats['matches'] >= 5:
            score += 1.0
        elif stats['matches'] >= 3:
            score += 0.7
        elif stats['matches'] >= 1:
            score += 0.4
        
        return min(score, 4.0)  # Максимум 4 балла за поведенческий рейтинг