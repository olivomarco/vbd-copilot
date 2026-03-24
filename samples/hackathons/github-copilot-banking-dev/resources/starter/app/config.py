from __future__ import annotations

import os
from typing import List


class Settings:
    """Application settings loaded from environment variables.

    All values default to development-safe settings. Production deployments
    must override FINCORE_SECRET_KEY and FINCORE_DATABASE_URL at minimum.
    """

    secret_key: str = os.environ.get(
        "FINCORE_SECRET_KEY",
        "insecure-dev-key-do-not-use-in-production",
    )
    database_url: str = os.environ.get(
        "FINCORE_DATABASE_URL",
        "sqlite:///./fincore.db",
    )
    environment: str = os.environ.get("FINCORE_ENVIRONMENT", "development")
    log_level: str = os.environ.get("FINCORE_LOG_LEVEL", "INFO")
    jwt_expiry_minutes: int = int(os.environ.get("FINCORE_JWT_EXPIRY_MINUTES", "60"))
    allowed_origins: List[str] = os.environ.get(
        "FINCORE_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:8000",
    ).split(",")

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


settings = Settings()
