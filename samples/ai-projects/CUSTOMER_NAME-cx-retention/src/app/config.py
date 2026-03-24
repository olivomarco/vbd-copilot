"""Application configuration loaded from environment variables.

Uses pydantic-settings BaseSettings for type-safe configuration with
automatic environment variable binding. All Azure authentication is
handled via DefaultAzureCredential (Managed Identity) -- no API keys
are stored in configuration.
"""

from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the Bill Explainer backend.

    Every field maps to an environment variable of the same name
    (case-insensitive). Defaults are provided where safe; service
    endpoints must be supplied at deployment time.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- Azure OpenAI ----------------------------------------------------------
    azure_openai_endpoint: str
    azure_openai_gpt4o_deployment: str = "gpt-4o"
    azure_openai_gpt4o_mini_deployment: str = "gpt-4o-mini"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    # -- Azure AI Search -------------------------------------------------------
    azure_search_endpoint: str
    azure_search_index_name: str = "knowledge-base"

    # -- Azure Cosmos DB -------------------------------------------------------
    cosmos_db_endpoint: str
    cosmos_db_database_name: str = "billexplainer"

    # -- CUSTOMER_NAME Billing API -------------------------------------------------
    billing_api_base_url: str
    billing_api_client_id: str
    billing_api_scope: str

    # -- Azure Key Vault -------------------------------------------------------
    key_vault_url: str

    # -- Observability ---------------------------------------------------------
    app_insights_connection_string: Optional[str] = None

    # -- Application -----------------------------------------------------------
    log_level: str = "INFO"
    cors_allowed_origins: str = "http://localhost:8000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    """Factory that creates a Settings instance (reads env once)."""
    return Settings()  # type: ignore[call-arg]
