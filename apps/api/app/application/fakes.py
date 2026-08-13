"""In-memory implementations of application ports for use-case tests.

These fakes deliberately live in the application test-support boundary: use-case
contracts can be exercised without PostgreSQL, Git, tree-sitter, Redis, or an
LLM provider.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any


class InMemoryRepoStore:
    def __init__(self) -> None:
        self.entities: dict[str, Any] = {}

    def get_repository(self, repository_id: str) -> Any | None:
        return self.entities.get(repository_id)

    def save(self, entity: Any) -> None:
        self.entities[entity["id"]] = entity


class InMemorySourceControl:
    def __init__(self, revision: str = "in-memory-revision") -> None:
        self.revision = revision
        self.clones: list[tuple[str, Path, str | None]] = []

    def clone(self, clone_url: str, destination: Path, revision: str | None = None) -> str:
        self.clones.append((clone_url, destination, revision))
        return revision or self.revision


class InMemoryLexicalSearch:
    def __init__(self, results: Sequence[Any] = ()) -> None:
        self.results = list(results)

    def search(self, query: str, *, repository_ids: Sequence[str] = (), limit: int = 20) -> Sequence[Any]:
        return self.results[:limit]


class InMemoryVectorSearch:
    def __init__(self, results: Sequence[Any] = ()) -> None:
        self.results = list(results)

    def search(self, vector: Sequence[float], *, repository_ids: Sequence[str] = (), limit: int = 20) -> Sequence[Any]:
        return self.results[:limit]


class InMemoryCodeParser:
    def analyze(self, source: str, language: str) -> Any:
        return {"source": source, "language": language}


class InMemoryLLM:
    def __init__(self, response: Any = None) -> None:
        self.response = response
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, schema: type[Any] | None = None) -> Any:
        self.prompts.append(prompt)
        return self.response


class InMemoryEmbeddings:
    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return [[float(len(text))] for text in texts]


class InMemoryJobQueue:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def enqueue(self, job: str, *args: Any, **kwargs: Any) -> Any:
        record = (job, args, kwargs)
        self.jobs.append(record)
        return record
