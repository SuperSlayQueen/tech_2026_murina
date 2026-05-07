import asyncio
import logging
from sqlalchemy import select

from src.backend.database import async_session_maker
from src.backend.models import Rating, User, Event
from src.services.rating_calculator import RatingCalculator
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)
rating_calculator = RatingCalculator()


async def _recalculate_all_ratings() -> int:
    updated = 0
    async with async_session_maker() as session:
        users_result = await session.execute(select(User.id))
        user_ids = [row[0] for row in users_result.all()]

        for user_id in user_ids:
            await rating_calculator.update_rating(session, user_id)
            updated += 1
    return updated


async def _process_pending_events() -> int:
    processed = 0
    async with async_session_maker() as session:
        events_result = await session.execute(
            select(Event).where(Event.processed.is_(False)).order_by(Event.created_at.asc()).limit(500)
        )
        events = events_result.scalars().all()

        impacted_users: set[int] = set()
        for event in events:
            payload = event.payload or {}
            if event.event_type == "like":
                if "to_user_id" in payload:
                    impacted_users.add(payload["to_user_id"])
                if "from_user_id" in payload:
                    impacted_users.add(payload["from_user_id"])
            elif event.event_type == "match":
                if "user1_id" in payload:
                    impacted_users.add(payload["user1_id"])
                if "user2_id" in payload:
                    impacted_users.add(payload["user2_id"])
            event.processed = True
            processed += 1

        for user_id in impacted_users:
            rating_result = await session.execute(select(Rating).where(Rating.user_id == user_id))
            if rating_result.scalar_one_or_none() is not None:
                await rating_calculator.update_rating(session, user_id)
    return processed


@celery_app.task(name="src.tasks.tasks.recalculate_all_ratings")
def recalculate_all_ratings() -> str:
    updated = asyncio.run(_recalculate_all_ratings())
    message = f"Ratings recalculated for {updated} users"
    logger.info(message)
    return message


@celery_app.task(name="src.tasks.tasks.process_pending_events")
def process_pending_events() -> str:
    processed = asyncio.run(_process_pending_events())
    message = f"Processed {processed} pending events"
    logger.info(message)
    return message
