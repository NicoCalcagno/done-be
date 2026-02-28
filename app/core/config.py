from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    POSTGRES_USER: str = "done"
    POSTGRES_PASSWORD: str = "done"
    POSTGRES_DB: str = "done"
    DATABASE_URL: str = "postgresql://done:done@db:5432/done"
    SECRET_KEY: str = "changeme"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    OPENAI_API_KEY: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
