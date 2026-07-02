from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://postgres:password@localhost:5432/fertilizer_crm"

    class Config:
        env_file = ".env"

    @property
    def db_url(self) -> str:
        # Railway injects DATABASE_URL as postgresql:// — convert for psycopg2
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url


settings = Settings()
