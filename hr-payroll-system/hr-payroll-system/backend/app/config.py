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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
