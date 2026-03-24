from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8200
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]


settings = Settings()
