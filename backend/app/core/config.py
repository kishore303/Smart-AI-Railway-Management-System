from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    database_url: str = Field(default="postgresql+psycopg2://postgres:postgres@localhost:5432/sih26027")
    database_url_async: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/sih26027")
    jwt_secret_key: str = Field(default="dev-only-not-for-production-change-me-32chars!")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=1440)
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: str = Field(default="redis://localhost:6379/0")
    celery_result_backend: str = Field(default="redis://localhost:6379/0")
    app_env: str = Field(default="development")
    app_name: str = Field(default="SIH26027 Railway Block Planning")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000")
    model_artifacts_dir: str = Field(default="./model_artifacts")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
