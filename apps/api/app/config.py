from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://knowledgeway:knowledgeway@localhost:5432/knowledgeway"
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    repository_storage_path: str = "/data/repositories"
    max_file_size: int = 1_048_576
    embedding_batch_size: int = 32
    chat_context_limit: int = 12_000
    cors_origins: str = "http://localhost:3000"
settings = Settings()
