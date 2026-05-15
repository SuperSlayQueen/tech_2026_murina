import asyncio
import logging
from sqlalchemy import select

from src.backend.database import async_session_maker
from src.backend.models import Rating, User
from src.services.cache import CacheService
from src.services.rating_calculator import RatingCalculator
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)
rating_calculator = RatingCalculator()


async def _update_ratings_for_users(user_ids: list[int]) -> int:
    updated = 0
    async with async_session_maker() as session:
        for user_id in user_ids:
            rating_result = await session.execute(select(Rating).where(Rating.user_id == user_id))
            if rating_result.scalar_one_or_none() is not None:
                await rating_calculator.update_rating(session, user_id)
                updated += 1
    return updated


async def _invalidate_search_data(telegram_ids: list[int]) -> None:
    cache = CacheService()
    try:
        for telegram_id in telegram_ids:
            if telegram_id:
                await cache.invalidate_user_search_data(telegram_id)
    finally:
        await cache.close()


async def _recalculate_all_ratings() -> int:
    updated = 0
    async with async_session_maker() as session:
        users_result = await session.execute(select(User.id))
        user_ids = [row[0] for row in users_result.all()]

        for user_id in user_ids:
            await rating_calculator.update_rating(session, user_id)
            updated += 1

    cache = CacheService()
    try:
        await cache.invalidate_all_profile_caches()
    finally:
        await cache.close()

    return updated


async def _handle_like_event(
    from_user_id: int,
    to_user_id: int,
    from_telegram_id: int,
    to_telegram_id: int,
) -> int:
    updated = await _update_ratings_for_users([from_user_id, to_user_id])
    await _invalidate_search_data([from_telegram_id, to_telegram_id])
    return updated


async def _handle_match_event(
    user1_id: int,
    user2_id: int,
    user1_telegram_id: int,
    user2_telegram_id: int,
) -> int:
    updated = await _update_ratings_for_users([user1_id, user2_id])
    await _invalidate_search_data([user1_telegram_id, user2_telegram_id])
    return updated


@celery_app.task(name="src.tasks.tasks.handle_like_event")
def handle_like_event(
    from_user_id: int,
    to_user_id: int,
    from_telegram_id: int,
    to_telegram_id: int,
) -> str:
    updated = asyncio.run(
        _handle_like_event(from_user_id, to_user_id, from_telegram_id, to_telegram_id)
    )
    message = f"Like event processed, ratings updated for {updated} users"
    logger.info(message)
    return message


@celery_app.task(name="src.tasks.tasks.handle_match_event")
def handle_match_event(
    user1_id: int,
    user2_id: int,
    user1_telegram_id: int,
    user2_telegram_id: int,
) -> str:
    updated = asyncio.run(
        _handle_match_event(user1_id, user2_id, user1_telegram_id, user2_telegram_id)
    )
    message = f"Match event processed, ratings updated for {updated} users"
    logger.info(message)
    return message


@celery_app.task(name="src.tasks.tasks.recalculate_all_ratings")
def recalculate_all_ratings() -> str:
    updated = asyncio.run(_recalculate_all_ratings())
    message = f"Ratings recalculated for {updated} users, Redis caches cleared"
    logger.info(message)
    return message
