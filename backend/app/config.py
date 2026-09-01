from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

# Current file:
# D:\ReviveAI\backend\app\config.py
#
# parents[0] -> D:\ReviveAI\backend\app
# parents[1] -> D:\ReviveAI\backend
# parents[2] -> D:\ReviveAI
PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_FILE = PROJECT_ROOT / ".env"


# ---------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------

load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    """
    Central application configuration.
    """

    app_name: str = "ReviveAI"
    app_env: str = "development"

    razorpay_key_id: str
    razorpay_key_secret: str
    razorpay_webhook_secret: str

    recovery_token_secret: str
    recovery_token_ttl_seconds: int = 1800

    database_url: str | None = None
    llm_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()