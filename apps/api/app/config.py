from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://knowledgeway:knowledgeway@localhost:5432/knowledgeway"
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4.1-mini"
    # Semantic retrieval is opt-in. "none" makes no embedding network requests.
    embedding_provider: str = "none"
    embedding_batch_size: int = 32
    openrouter_api_key: str | None = None
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Reserved for a future paid reranker integration; no reranking request is made yet.
    rerank_provider: str = "none"
    rerank_model: str | None = None
    repository_storage_path: str = "/data/repositories"
    max_file_size: int = 1_048_576
    chat_context_limit: int = 12_000
    cors_origins: str = "http://localhost:3000"
    # Mount these read-only from a secret store; never put Git credentials in URLs.
    git_ssh_key_path: str | None = None
    git_ssh_known_hosts_path: str | None = None
    git_https_token_file: str | None = None
    git_https_username: str = "x-access-token"
    git_https_askpass_path: str = "/app/app/git_askpass.py"


settings = Settings()
