from pydantic_settings import BaseSettings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # China data
    tushare_token: str = ""
    polygon_api_key: str = ""
    # AI (MiniMax via Anthropic-compatible endpoint)
    minimax_api_key: str = ""
    # Auth
    jwt_secret: str = "dev-secret-change-in-production"
    # Database
    database_path: str = str(PROJECT_ROOT / "pokieticker.db")

    model_config = {"env_file": str(PROJECT_ROOT / ".env"), "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
