from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env lives at the repo root; extra="ignore" lets it hold keys other tools read
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore"
    )

    openaq_api_key: str
    center_lat: float
    center_lon: float


settings = Settings()
