from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Stock Guidance Platform"
    debug: bool = False

    # Database
    postgres_user: str = "stockguidance"
    postgres_password: str = "changeme"
    postgres_db: str = "stockguidance"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = "change-me-to-a-random-string"

    # LLM — DeepSeek V4 Flash (non-thinking mode)
    deepseek_api_key: str = ""

    # Financial data — Twelve Data (free tier: 800 req/day)
    # Get your key at https://twelvedata.com
    twelvedata_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
