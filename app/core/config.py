"""
Application configuration using Pydantic Settings
"""
import json
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/globant_challenge"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "globant_challenge"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    log_level: str = "INFO"
    
    # Security
    secret_key: str = "your-secret-key-here-change-in-production"
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    # Comma-separated list of valid API keys (simple shared-secret auth)
    api_keys: List[str] = ["local-dev-key"]
    
    # File Upload
    max_upload_size: int = 2147483648  # 2GB
    chunk_size: int = 8388608  # 8MB
    
    # Performance
    batch_size: int = 50000
    copy_buffer_size: int = 65536
    
    # Monitoring
    enable_metrics: bool = True
    enable_tracing: bool = False
    
    @field_validator("cors_origins", mode="before")
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]
        return v

    @field_validator("api_keys", mode="before")
    def parse_api_keys(cls, v):
        """Allow API_KEYS to be provided as JSON list or comma-separated string."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [key.strip() for key in v.split(",") if key.strip()]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings() 