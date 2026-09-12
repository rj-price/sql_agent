import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    SQL_HOST: str = os.getenv("SQL_HOST", "localhost")
    SQL_USER: str = os.getenv("SQL_USER", "root")
    SQL_PASSWORD: str = os.getenv("SQL_PASSWORD", "")
    SQL_DATABASE: str = os.getenv("SQL_DATABASE", "")
    SQL_PORT: int = int(os.getenv("SQL_PORT", 3306))
    # Langfuse tracing: enabled only when both keys are set
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "http://192.168.1.100:3040")

    class Config:
        env_file = ".env"

settings = Settings()
