"""Configuration management via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-20240307"

    # GitHub
    github_token: str = ""

    # Review thresholds
    max_findings_per_agent: int = 20
    min_severity_to_post: str = "LOW"  # LOW | MEDIUM | HIGH

    @property
    def severity_levels(self) -> list[str]:
        """Return severity levels at or above the minimum."""
        order = ["LOW", "MEDIUM", "HIGH"]
        idx = order.index(self.min_severity_to_post)
        return order[idx:]


settings = Settings()
