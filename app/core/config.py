from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./gestor_noticias.db"
    SECRET_KEY: str = "cambiar-esta-clave-en-produccion"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM Configuration (Forzamos valores de producción para evitar problemas con Railway)
    LLM_PROVIDER: str = "opencode"
    LLM_API_KEY: str = "sk-2j1GQbg61s8pd66gTIIBxUXlirTvXAg95DG1k1y2FJocA3DR6hm1KAyGHr3pOjOr"
    LLM_MODEL: str = "big-pickle"
    LLM_BASE_URL: str = "https://opencode.ai/zen/v1"

    # Railway uses $PORT
    PORT: int = 8000

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
