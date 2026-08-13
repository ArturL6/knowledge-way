"""Application-layer ports.

Ports describe capabilities required by use cases without coupling them to HTTP,
PostgreSQL, tree-sitter, Redis, or provider SDKs.  Concrete implementations
live under :mod:`app.adapters.outbound`.
"""

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RepoStore(Protocol):
    """Persistence operations for repositories and indexed facts."""

    def get_repository(self, repository_id: str) -> Any | None: ...
    def save(self, entity: Any) -> None: ...


@runtime_checkable
class SourceControl(Protocol):
    """Clone and inspect a source-control revision."""

    def clone(self, clone_url: str, destination: Path, revision: str | None = None) -> str: ...


@runtime_checkable
class LexicalSearch(Protocol):
    """Search exact and lexical code representations."""

    def search(self, query: str, *, repository_ids: Sequence[str] = (), limit: int = 20) -> Sequence[Any]: ...


@runtime_checkable
class VectorSearch(Protocol):
    """Search embedded representations."""

    def search(self, vector: Sequence[float], *, repository_ids: Sequence[str] = (), limit: int = 20) -> Sequence[Any]: ...


@runtime_checkable
class CodeParser(Protocol):
    """Extract deterministic facts from a source file."""

    def analyze(self, source: str, language: str) -> Any: ...


@runtime_checkable
class LLM(Protocol):
    """Generate an optional structured narrative."""

    def complete(self, prompt: str, *, schema: type[Any] | None = None) -> Any: ...


@runtime_checkable
class Embeddings(Protocol):
    """Embed text without exposing a provider SDK to use cases."""

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


@runtime_checkable
class JobQueue(Protocol):
    """Enqueue background application work."""

    def enqueue(self, job: str, *args: Any, **kwargs: Any) -> Any: ...


__all__ = [
    "CodeParser", "Embeddings", "JobQueue", "LLM", "LexicalSearch",
    "RepoStore", "SourceControl", "VectorSearch",
]
