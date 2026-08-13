from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# A bare ".env" resolves against the working directory, so it found nothing whenever a script or
# pytest ran from anywhere but the repository root and every setting silently fell back to its
# default. Search upward for the file instead of assuming a depth: the image lays the package out
# as /app/app, the repository as apps/api/app. None means "no file", which is correct in Docker
# where compose injects the values as real environment variables -- and those win over any file.
_ENV_FILE = next(
    (parent / ".env" for parent in Path(__file__).resolve().parents if (parent / ".env").is_file()),
    None,
)

# Also load it into os.environ, so code that reads the environment directly rather than through
# Settings sees the same values (alembic's env.py, GOOGLE_APPLICATION_CREDENTIALS, any script).
# override=False keeps a real environment variable authoritative, which is what makes the compose
# `env_file:` injection win inside Docker.
if _ENV_FILE:
    load_dotenv(_ENV_FILE, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

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
    # text-embedding-3-small rejects any input over 8192 tokens. Source code runs near three
    # characters per token, so this keeps the worst case inside the ceiling with margin.
    embedding_max_input_characters: int = 20_000
    # Vertex uses Google Application Default Credentials; mount them read-only in Docker.
    vertex_project_id: str | None = None
    vertex_location: str = "us-central1"
    vertex_embedding_model: str = "text-embedding-005"
    vertex_embedding_dimensions: int = 768
    # Optional, versioned LLM summaries of symbols. Explicit opt-in because they incur usage costs.
    code_cards_enabled: bool = False
    # "vertex" uses ADC and Gemini; "openrouter" reuses OPENROUTER_API_KEY. The model must support
    # structured outputs, because a card is only persisted if it validates against CodeCardDetails.
    code_card_provider: str = "openrouter"
    openrouter_card_model: str = "deepseek/deepseek-v4-flash-0731"
    vertex_gemini_location: str = "global"
    vertex_gemini_model: str = "gemini-3.5-flash"
    code_card_max_source_characters: int = 12000
    # Bounded in-flight Gemini requests. Keep this deliberately small to respect quota.
    code_card_request_concurrency: int = 8
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
    git_https_askpass_path: str = "/app/app/adapters/outbound/git_cli/git_askpass.py"


settings = Settings()
