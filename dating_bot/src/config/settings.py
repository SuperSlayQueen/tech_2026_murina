from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Telegram Bot
    bot_token: str = Field(..., env="BOT_TOKEN")
    
    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    
    # Redis
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_db: int = Field(default=0, env="REDIS_DB")
    
    # RabbitMQ
    rabbitmq_host: str = Field(default="localhost", env="RABBITMQ_HOST")
    rabbitmq_port: int = Field(default=5672, env="RABBITMQ_PORT")
    rabbitmq_user: str = Field(default="guest", env="RABBITMQ_USER")
    rabbitmq_password: str = Field(default="guest", env="RABBITMQ_PASSWORD")
    
    # S3 (Minio)
    minio_endpoint: str = Field(default="localhost:9000", env="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="minioadmin", env="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="minioadmin", env="MINIO_SECRET_KEY")
    minio_bucket: str = Field(default="dating-bot", env="MINIO_BUCKET")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
