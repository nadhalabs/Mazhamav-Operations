from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Mazha Mav Operations API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/mazhamav"
    jwt_secret: str = "development-only-secret-change-this"
    access_token_minutes: int = 480
    business_timezone: str = "Asia/Kolkata"
    frontend_origin: str = "http://localhost:3000"
    secure_cookies: bool = False
    seed_owner_phone: str = "9999999999"
    seed_owner_password: str = "ChangeMe123!"
    staff_can_create_retailers: bool = True
    media_storage_backend: str = "local"
    media_local_path: str = "media"
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    max_qr_upload_bytes: int = 5_000_000
    login_rate_limit_attempts: int = 10
    login_rate_limit_window_seconds: int = 300
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def production_guards(self):
        if self.environment == "production":
            if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("development"):
                raise ValueError("Production JWT_SECRET must be a strong secret of at least 32 characters")
            if not self.secure_cookies:
                raise ValueError("SECURE_COOKIES must be true in production")
            if self.media_storage_backend != "s3" or not self.s3_bucket:
                raise ValueError("Production media storage must use a configured S3-compatible bucket")
            if not self.frontend_origin.startswith("https://"):
                raise ValueError("Production FRONTEND_ORIGIN must use HTTPS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
