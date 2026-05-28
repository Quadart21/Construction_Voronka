from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parent.parent
_VERSION_FILE = _ROOT / "VERSION"


def read_app_version() -> str:
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Instagram Telegram Funnel"
    app_version: str = read_app_version()
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "sqlite:///./data/funnel.db"
    bot_token: str = Field(default="", alias="BOT_TOKEN")
    admin_ids: str = "6132866588"
    admin_panel_username: str = "admin"
    admin_panel_password: str = "admin123"
    public_bot_url: str = "https://t.me/your_bot"
    platega_base_url: str = "https://app.platega.io"
    platega_merchant_id: str = ""
    platega_secret: str = ""
    platega_return_url: str = "https://example.com/payment/success"
    platega_failed_url: str = "https://example.com/payment/fail"
    platega_callback_url: str = ""
    default_discount_percent: int = 20
    default_discount_window_hours: int = 4
    anti_spam_window_seconds: int = 5
    anti_spam_burst_limit: int = 6
    nurture_enabled: bool = True
    content_protection_enabled: bool = True
    timezone: str = "Europe/Amsterdam"
    data_dir: Path = Path("data")
    upload_dir: Path = Path("data/uploads")
    admin_jwt_secret: str = Field(default="", alias="ADMIN_JWT_SECRET")
    admin_access_token_days: int = Field(default=30, alias="ADMIN_ACCESS_TOKEN_DAYS")

    @property
    def admin_id_list(self) -> list[int]:
        return [int(item.strip()) for item in self.admin_ids.split(",") if item.strip()]

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"debug", "dev", "development"}:
                return True
        return value


settings = Settings()
