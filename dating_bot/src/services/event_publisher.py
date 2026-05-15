"""Публикация событий в RabbitMQ через Celery."""
import logging

logger = logging.getLogger(__name__)


def publish_like_event(
    from_user_id: int,
    to_user_id: int,
    from_telegram_id: int,
    to_telegram_id: int,
) -> None:
    from src.tasks.tasks import handle_like_event

    handle_like_event.delay(
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        from_telegram_id=from_telegram_id,
        to_telegram_id=to_telegram_id,
    )
    logger.info(
        "Событие like отправлено в RabbitMQ: %s -> %s",
        from_user_id,
        to_user_id,
    )


def publish_match_event(
    user1_id: int,
    user2_id: int,
    user1_telegram_id: int,
    user2_telegram_id: int,
) -> None:
    from src.tasks.tasks import handle_match_event

    handle_match_event.delay(
        user1_id=user1_id,
        user2_id=user2_id,
        user1_telegram_id=user1_telegram_id,
        user2_telegram_id=user2_telegram_id,
    )
    logger.info(
        "Событие match отправлено в RabbitMQ: %s <-> %s",
        user1_id,
        user2_id,
    )
