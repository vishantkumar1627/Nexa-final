import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the backend folder if it exists
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "AI Text-to-3D Floor Plan System")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

    # Database
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "architecture_db")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "db")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    
    # SQLAlchemy URLs
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    SYNC_DATABASE_URL: str = os.getenv(
        "SYNC_DATABASE_URL", 
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )

    # Redis & Broker
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

    # JWT Security
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "9a3dfbe48f95c1d683719485bb29e0018f2f9c8da9e06180a0684f88427fbf02")
    JWT_REFRESH_SECRET_KEY: str = os.getenv("JWT_REFRESH_SECRET_KEY", "e83a992a7e7b5abfa34ff6c6a47ea1e389d020fb143c1ab2f20c4ef18671607a")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # File Storage
    STORAGE_DIR: str = os.getenv("STORAGE_DIR", "/app/outputs")
    USE_S3: bool = os.getenv("USE_S3", "False").lower() in ("true", "1", "yes")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_BUCKET_NAME: str = os.getenv("AWS_BUCKET_NAME", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")

    # Supabase Storage
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_JWT_KEY: str = os.getenv("SUPABASE_JWT_KEY", "")
    SUPABASE_BUCKET: str = os.getenv("SUPABASE_BUCKET", "DeepInsights")
    USE_SUPABASE: bool = bool(os.getenv("SUPABASE_URL", ""))

    # LLM Provider
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "Claude")
    LLM_PROVIDER_MODE: str = os.getenv("LLM_PROVIDER_MODE", "regex")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    # CLAUDE_API_KEY is stored as ANTHROPIC_API_KEY in the Anthropic SDK convention
    ANTHROPIC_API_KEY: str = os.getenv("CLAUDE_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

settings = Settings()
