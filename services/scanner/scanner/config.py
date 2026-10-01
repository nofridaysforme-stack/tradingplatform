"""Environment settings for the scanner (spec 16). Secrets never leave this process."""

from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

OANDA_HOSTS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}
MASSIVE_HOST = "https://api.massive.com"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    oanda_api_token: SecretStr | None = None
    oanda_account_id: str | None = None
    oanda_env: Literal["practice", "live"] = "practice"
    massive_api_key: SecretStr | None = None
    log_level: str = "info"

    @property
    def oanda_host(self) -> str:
        return OANDA_HOSTS[self.oanda_env]
