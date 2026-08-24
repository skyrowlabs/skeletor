"""Environment config. No pydantic-settings dependency -- four values do not
justify one, and every dependency is a thing that can fail to install."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    app_name: str
    app_purpose: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ.get(
                "DATABASE_URL", "postgresql+psycopg://app:app@db:5432/app"
            ),
            app_name=os.environ.get("APP_NAME", "@@APP_NAME@@"),
            app_purpose=os.environ.get("APP_PURPOSE", "@@APP_PURPOSE@@"),
        )


settings = Settings.from_env()
