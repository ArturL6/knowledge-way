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
    # Vertex uses Google Application Default Credentials; mount them read-only in Docker.
    vertex_project_id: str | None = None
    vertex_location: str = "us-central1"
    vertex_embedding_model: str = "text-embedding-005"
    vertex_embedding_dimensions: int = 768
    # Optional, versioned Gemini summaries of symbols. Explicit opt-in because they incur usage costs.
    code_cards_enabled: bool = False
    vertex_gemini_location: str = "global"
    vertex_gemini_model: str = "gemini-3.5-flash"
    code_card_max_source_characters: int = 12000
    # Reranking is opt-in per query and runs only over a bounded retrieval candidate set.
    rerank_provider: str = "none"
    rerank_model: str | None = None
    cohere_api_key: str | None = None
    rerank_candidate_limit: int = 40
    repository_storage_path: str = "/data/repositories"
    max_file_size: int = 1_048_576
    # Full parser-graph rebuilds for large repositories can exceed RQ's default timeout.
    index_job_timeout: int = 1_800
    chat_context_limit: int = 12_000
    cors_origins: str = "http://localhost:3000"
    # Mount these read-only from a secret store; never put Git credentials in URLs.
    git_ssh_key_path: str | None = None
    git_ssh_known_hosts_path: str | None = None
    git_https_token_file: str | None = None
    git_https_username: str = "x-access-token"
    git_https_askpass_path: str = "/app/app/git_askpass.py"


settings = Settings()
