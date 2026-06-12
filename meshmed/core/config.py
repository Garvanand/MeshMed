"""
MeshMed Application Configuration.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # LLM APIs
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    
    # DB & Infrastructure
    redis_url: str = "redis://localhost:6379/0"
    postgres_url: str = "postgresql+asyncpg://agentos:agentos_password@localhost:5432/agentos_shared"
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    
    # Security
    phi_encryption_key: str = "" # Critical: Must be 32-byte base64 encoded Fernet key
    agentos_internal_service_token: str = ""
    
    # External Integrations
    whatsapp_api_token: str = ""
    openfda_api_key: str = ""
    
    log_level: str = "INFO"
    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


_settings = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
