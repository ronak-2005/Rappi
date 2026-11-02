"""App settings read once from backend/.env (see .env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_path: str = "var/app.db"
    read_api_url: str = "http://localhost:8001"
    supplier_api_url: str = "http://localhost:8003"
    policy_path: str = "policy.yaml"
    fixtures_dir: str = "fixtures"
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"

    def resolve(self, relative: str) -> Path:
        """Paths in .env are relative to backend/."""
        path = Path(relative)
        return path if path.is_absolute() else BACKEND_DIR / path

    @property
    def db_file(self) -> Path:
        return self.resolve(self.database_path)

    @property
    def var_dir(self) -> Path:
        return BACKEND_DIR / "var"


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
