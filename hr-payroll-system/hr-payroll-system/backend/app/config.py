from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Reads values from environment variables or the backend/.env file."""

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    frontend_origin: str = "http://localhost:5173"
    company_timezone: str = "UTC"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"

    # ---------------------------------------------------- QR attendance module
    qr_signing_secret: str = ""            # HMAC key for QR payloads; falls back to jwt_secret
    qr_dynamic_ttl_seconds: int = 300      # lifetime of a dynamic (rotating) QR code
    qr_clock_skew_seconds: int = 30        # tolerated clock drift on the kiosk
    qr_challenge_ttl_seconds: int = 90     # how long a "enter your PIN" prompt stays open
    qr_max_pin_attempts: int = 5           # wrong PINs before the credential is locked
    qr_pin_lockout_seconds: int = 900      # lockout duration after too many wrong PINs
    qr_scan_rate_per_minute: int = 12      # scans per employee per minute
    qr_kiosk_rate_per_minute: int = 60     # scans per kiosk per minute
    qr_max_punches_per_day: int = 20       # hard cap on punches per employee per day
    qr_min_punch_interval_seconds: int = 30  # ignore a second scan that comes too fast

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
