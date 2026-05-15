from datetime import datetime
from sqlalchemy import (
    Integer,
    BigInteger,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    JSON,
    Float,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.backend.database import Base


class User(Base):
    """Пользователь бота"""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связи
    profile: Mapped["Profile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    ratings: Mapped[list["Rating"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id})>"


class Profile(Base):
    """Анкета пользователя"""
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("age >= 16 AND age <= 100", name="check_profile_age_range"),
        Index("idx_profiles_gender_city", "gender", "city"),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)  # male, female
    search_gender: Mapped[str] = mapped_column(String(20), default='all')  # male, female, all - кого ищет
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    bio: Mapped[str] = mapped_column(String(500), nullable=True)
    photo_id: Mapped[str] = mapped_column(String(255), nullable=True)
    photos_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    user: Mapped["User"] = relationship(back_populates="profile")
    photos: Mapped[list["ProfilePhoto"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="ProfilePhoto.position"
    )


class ProfilePhoto(Base):
    """Фотографии анкеты (до 3 штук)"""
    __tablename__ = "profile_photos"
    __table_args__ = (
        UniqueConstraint("profile_id", "position", name="uq_profile_photo_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profile: Mapped["Profile"] = relationship(back_populates="photos")


class Like(Base):
    """Лайк пользователя"""
    __tablename__ = "likes"
    __table_args__ = (
        UniqueConstraint("from_user_id", "to_user_id", name="uq_like_from_to"),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    to_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<Like(from={self.from_user_id}, to={self.to_user_id})>"


class Match(Base):
    """Взаимный лайк (мэтч)"""
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("user1_id", "user2_id", name="uq_match_pair"),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user1_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user2_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Match(user1={self.user1_id}, user2={self.user2_id})>"


class Rating(Base):
    """Рейтинг пользователя"""
    __tablename__ = "ratings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    primary_score: Mapped[float] = mapped_column(Float, default=0.0)  # Первичный рейтинг
    behavior_score: Mapped[float] = mapped_column(Float, default=0.0)  # Поведенческий рейтинг
    total_score: Mapped[float] = mapped_column(Float, default=0.0)  # Итоговый рейтинг
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    user: Mapped["User"] = relationship(back_populates="ratings")
    
    def __repr__(self):
        return f"<Rating(user_id={self.user_id}, total={self.total_score})>"


class Event(Base):
    """Событие для обработки через RabbitMQ"""
    __tablename__ = "events"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # like, match, rating_update
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    
    def __repr__(self):
        return f"<Event(type={self.event_type}, processed={self.processed})>"