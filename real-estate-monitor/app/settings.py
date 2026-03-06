"""
Application settings using Pydantic v2 Settings.
All configuration loaded from environment variables.
"""
import json
from typing import Optional, List, Dict, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    
    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_name: str = Field(default="real-estate-monitor", alias="APP_NAME")
    app_env: str = Field(default="production", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/realestate",
        alias="DATABASE_URL"
    )
    database_url_sync: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/realestate",
        alias="DATABASE_URL_SYNC"
    )
    
    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1", alias="CELERY_BROKER_URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2", alias="CELERY_RESULT_BACKEND"
    )
    
    # -------------------------------------------------------------------------
    # WhatsApp Cloud API
    # -------------------------------------------------------------------------
    wa_token: Optional[str] = Field(default=None, alias="WA_TOKEN")
    wa_phone_number_id: Optional[str] = Field(default=None, alias="WA_PHONE_NUMBER_ID")
    wa_to: Optional[str] = Field(default=None, alias="WA_TO")
    
    # -------------------------------------------------------------------------
    # Facebook Cookies for session injection
    # -------------------------------------------------------------------------
    fb_cookies_json: List[Dict[str, Any]] = Field(default_factory=list, alias="FB_COOKIES_JSON")
    
    @field_validator("fb_cookies_json", mode="before")
    @classmethod
    def parse_fb_cookies(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v) if v.strip() else []
            except json.JSONDecodeError:
                return []
        return v or []
    
    # -------------------------------------------------------------------------
    # Otodom Publication Integration
    # -------------------------------------------------------------------------
    otodom_api_base_url: Optional[str] = Field(default=None, alias="OTODOM_API_BASE_URL")
    otodom_client_id: Optional[str] = Field(default=None, alias="OTODOM_CLIENT_ID")
    otodom_client_secret: Optional[str] = Field(default=None, alias="OTODOM_CLIENT_SECRET")
    otodom_access_token: Optional[str] = Field(default=None, alias="OTODOM_ACCESS_TOKEN")
    otodom_refresh_token: Optional[str] = Field(default=None, alias="OTODOM_REFRESH_TOKEN")
    otodom_account_id: Optional[str] = Field(default=None, alias="OTODOM_ACCOUNT_ID")
    otodom_default_contact_name: Optional[str] = Field(default=None, alias="OTODOM_DEFAULT_CONTACT_NAME")
    otodom_default_contact_email: Optional[str] = Field(default=None, alias="OTODOM_DEFAULT_CONTACT_EMAIL")
    otodom_default_contact_phone: Optional[str] = Field(default=None, alias="OTODOM_DEFAULT_CONTACT_PHONE")
    otodom_request_timeout: int = Field(default=30000, alias="OTODOM_REQUEST_TIMEOUT")
    otodom_max_retries: int = Field(default=5, alias="OTODOM_MAX_RETRIES")

    # -------------------------------------------------------------------------
    # Source Configuration Overrides
    # -------------------------------------------------------------------------
    otodom_interval_seconds: int = Field(default=900, alias="OTODOM_INTERVAL_SECONDS")
    olx_interval_seconds: int = Field(default=900, alias="OLX_INTERVAL_SECONDS")
    facebook_interval_seconds: int = Field(default=1800, alias="FACEBOOK_INTERVAL_SECONDS")
    
    otodom_rate_limit_rps: float = Field(default=0.5, alias="OTODOM_RATE_LIMIT_RPS")
    olx_rate_limit_rps: float = Field(default=0.7, alias="OLX_RATE_LIMIT_RPS")
    facebook_rate_limit_rps: float = Field(default=0.2, alias="FACEBOOK_RATE_LIMIT_RPS")
    
    # -------------------------------------------------------------------------
    # Circuit Breaker
    # -------------------------------------------------------------------------
    circuit_breaker_failure_threshold: int = Field(
        default=10, alias="CIRCUIT_BREAKER_FAILURE_THRESHOLD"
    )
    circuit_breaker_recovery_timeout: int = Field(
        default=600, alias="CIRCUIT_BREAKER_RECOVERY_TIMEOUT"
    )
    
    # -------------------------------------------------------------------------
    # Retry Configuration
    # -------------------------------------------------------------------------
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    retry_backoff_factor: float = Field(default=2.0, alias="RETRY_BACKOFF_FACTOR")
    retry_min_wait: int = Field(default=1, alias="RETRY_MIN_WAIT")
    retry_max_wait: int = Field(default=60, alias="RETRY_MAX_WAIT")
    
    # -------------------------------------------------------------------------
    # Playwright
    # -------------------------------------------------------------------------
    playwright_headless: bool = Field(default=True, alias="PLAYWRIGHT_HEADLESS")
    playwright_timeout: int = Field(default=30000, alias="PLAYWRIGHT_TIMEOUT")
    playwright_navigation_timeout: int = Field(
        default=45000, alias="PLAYWRIGHT_NAVIGATION_TIMEOUT"
    )
    
    # -------------------------------------------------------------------------
    # API
    # -------------------------------------------------------------------------
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    
    # -------------------------------------------------------------------------
    # Scheduler
    # -------------------------------------------------------------------------
    scheduler_beat_interval: int = Field(default=10, alias="SCHEDULER_BEAT_INTERVAL")
    
    # -------------------------------------------------------------------------
    # Notification
    # -------------------------------------------------------------------------
    notification_max_retries: int = Field(default=8, alias="NOTIFICATION_MAX_RETRIES")
    notification_retry_delay: int = Field(default=300, alias="NOTIFICATION_RETRY_DELAY")
    
    # -------------------------------------------------------------------------
    # Email (SMTP)
    # -------------------------------------------------------------------------
    smtp_host: Optional[str] = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: Optional[str] = Field(default=None, alias="SMTP_USER")
    smtp_pass: Optional[str] = Field(default=None, alias="SMTP_PASS")
    from_email: Optional[str] = Field(default=None, alias="FROM_EMAIL")
    
    # -------------------------------------------------------------------------
    # Slack
    # -------------------------------------------------------------------------
    slack_webhook_url: Optional[str] = Field(default=None, alias="SLACK_WEBHOOK_URL")
    
    # -------------------------------------------------------------------------
    # Telegram
    # -------------------------------------------------------------------------
    telegram_bot_token: Optional[str] = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(default=None, alias="TELEGRAM_CHAT_ID")
    
    # -------------------------------------------------------------------------
    # Discord
    # -------------------------------------------------------------------------
    discord_webhook_url: Optional[str] = Field(default=None, alias="DISCORD_WEBHOOK_URL")
    
    # -------------------------------------------------------------------------
    # Proxy Configuration
    # -------------------------------------------------------------------------
    proxy_list: List[str] = Field(default_factory=list, alias="PROXY_LIST")
    
    @field_validator("proxy_list", mode="before")
    @classmethod
    def parse_proxy_list(cls, v):
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        return v or []
    
    # -------------------------------------------------------------------------
    # Google Maps API
    # -------------------------------------------------------------------------
    google_maps_api_key: Optional[str] = Field(default=None, alias="GOOGLE_MAPS_API_KEY")
    
    # -------------------------------------------------------------------------
    # Advanced Settings
    # -------------------------------------------------------------------------
    price_drop_threshold: float = Field(default=5.0, alias="PRICE_DROP_THRESHOLD")
    duplicate_similarity_threshold: float = Field(default=0.75, alias="DUPLICATE_SIMILARITY_THRESHOLD")
    image_analysis_enabled: bool = Field(default=True, alias="IMAGE_ANALYSIS_ENABLED")
    smart_filtering_enabled: bool = Field(default=True, alias="SMART_FILTERING_ENABLED")
    
    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"
    
    @property
    def whatsapp_enabled(self) -> bool:
        return all([
            self.wa_token,
            self.wa_phone_number_id,
            self.wa_to
        ])
    
    @property
    def email_enabled(self) -> bool:
        return all([
            self.smtp_host,
            self.smtp_user,
            self.smtp_pass
        ])
    
    @property
    def slack_enabled(self) -> bool:
        return self.slack_webhook_url is not None
    
    @property
    def telegram_enabled(self) -> bool:
        return self.telegram_bot_token is not None
    
    @property
    def discord_enabled(self) -> bool:
        return self.discord_webhook_url is not None
    
    @property
    def geocoding_enabled(self) -> bool:
        return self.google_maps_api_key is not None


# Global settings instance
settings = Settings()
