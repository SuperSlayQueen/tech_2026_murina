import asyncio

from src.services.rating_calculator import RatingCalculator
from src.services.ranking import RankingService


class StubProfile:
    def __init__(self, age: int, city: str | None, bio: str | None, photos_count: int):
        self.age = age
        self.city = city
        self.bio = bio
        self.photos_count = photos_count


def test_behavior_score_max_cap():
    calculator = RatingCalculator()
    score = calculator._calculate_behavior_score(
        {"likes_received": 100, "likes_given": 50, "matches": 20, "like_ratio": 0.99}
    )
    assert score == 4.0


def test_behavior_score_low_activity():
    calculator = RatingCalculator()
    score = calculator._calculate_behavior_score(
        {"likes_received": 0, "likes_given": 1, "matches": 0, "like_ratio": 0.05}
    )
    assert score == 0.0


def test_primary_score_city_and_profile_completeness():
    ranking = RankingService(cache_service=None)  # cache не используется в расчете score
    user = StubProfile(age=24, city="Moscow", bio="x", photos_count=1)
    target = StubProfile(age=25, city="moscow", bio="about me", photos_count=3)

    score = asyncio.run(ranking._calculate_primary_score(user, target))
    assert score >= 2.8
