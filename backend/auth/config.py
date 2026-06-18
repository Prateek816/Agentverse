from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    SECRET_KEY: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"
        extra = "ignore"


auth_settings = AuthSettings()