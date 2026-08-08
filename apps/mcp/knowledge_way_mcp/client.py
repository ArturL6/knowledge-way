"""Bounded, GET-only client for knowledge-way's public REST API."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

MAX_QUERY_LENGTH = 1_000
MAX_ID_LENGTH = 256
MAX_RESULTS = 50
MAX_DEPTH = 2
MAX_NODES = 100


class ConfigurationError(ValueError):
    """The MCP process does not have a safe API configuration."""


class InputError(ValueError):
    """A tool input is outside the deliberately small MCP contract."""


class APIError(RuntimeError):
    """The configured knowledge-way API could not fulfill a read request."""


@dataclass(frozen=True)
class APIRequest:
    method: str
    url: str
    headers: dict[str, str]


def configured_client_from_env() -> "KnowledgeWayClient":
    base_url = os.environ.get("KW_API_BASE_URL")
    if not base_url:
        raise ConfigurationError("KW_API_BASE_URL must be configured before starting the MCP server")
    return KnowledgeWayClient(base_url, os.environ.get("KW_API_BEARER_TOKEN"))


def _bounded_text(value: str, name: str, maximum: int, *, minimum: int = 1) -> str:
    if not isinstance(value, str) or not minimum <= len(value) <= maximum:
        raise InputError(f"{name} must be a string between {minimum} and {maximum} characters")
    if "\x00" in value:
        raise InputError(f"{name} must not contain NUL bytes")
    return value


def _bounded_int(value: int, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise InputError(f"{name} must be an integer between {minimum} and {maximum}")
    return value


class KnowledgeWayClient:
    """An intentionally narrow client: all requests are HTTP GETs to /api."""

    def __init__(self, base_url: str, bearer_token: str | None = None) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
            raise ConfigurationError("KW_API_BASE_URL must be an absolute http(s) URL without query or fragment")
        self.base_url = base_url.rstrip("/")
        # Accept both the API root (https://host) and the documented API base
        # (https://host/api) without ever constructing a duplicated /api/api path.
        self._base_includes_api = urlsplit(self.base_url).path.rstrip("/").endswith("/api")
        self.bearer_token = bearer_token

    def request_for(self, path: str, params: dict[str, Any] | None = None) -> APIRequest:
        if not path.startswith("/api/"):
            raise ValueError("only public /api read endpoints are permitted")
        suffix = path[4:] if self._base_includes_api else path
        url = f"{self.base_url}{suffix}"
        if params:
            url += "?" + urlencode(params)
        headers = {"Accept": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return APIRequest("GET", url, headers)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        spec = self.request_for(path, params)
        request = Request(spec.url, headers=spec.headers, method=spec.method)
        try:
            with urlopen(request, timeout=20) as response:  # nosec B310: operator-configured API URL
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1_000]
            raise APIError(f"knowledge-way API returned HTTP {exc.code}: {body}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise APIError(f"knowledge-way API request failed: {exc}") from exc

    def list_repositories(self) -> Any:
        return self._get("/api/repositories")

    def search_code(self, query: str, mode: str = "hybrid", limit: int = 20) -> Any:
        query = _bounded_text(query, "query", MAX_QUERY_LENGTH)
        if mode not in {"hybrid", "lexical", "symbols", "semantic"}:
            raise InputError("mode must be one of hybrid, lexical, symbols, or semantic")
        return self._get("/api/search", {"q": query, "mode": mode, "limit": _bounded_int(limit, "limit", 1, MAX_RESULTS)})

    def get_symbol(self, repository_id: str, symbol_id: str) -> Any:
        return self._get(self._symbol_path(repository_id, symbol_id))

    def get_callers(self, repository_id: str, symbol_id: str) -> Any:
        return self._get(self._symbol_path(repository_id, symbol_id) + "/callers")

    def get_callees(self, repository_id: str, symbol_id: str) -> Any:
        return self._get(self._symbol_path(repository_id, symbol_id) + "/callees")

    def get_subgraph(self, repository_id: str, symbol_id: str, depth: int = 1, max_nodes: int = 50) -> Any:
        return self._get(self._symbol_path(repository_id, symbol_id) + "/subgraph", {
            "depth": _bounded_int(depth, "depth", 1, MAX_DEPTH),
            "max_nodes": _bounded_int(max_nodes, "max_nodes", 1, MAX_NODES),
        })

    @staticmethod
    def _symbol_path(repository_id: str, symbol_id: str) -> str:
        repository_id = _bounded_text(repository_id, "repository_id", MAX_ID_LENGTH)
        symbol_id = _bounded_text(symbol_id, "symbol_id", MAX_ID_LENGTH)
        return "/api/repositories/{}/symbols/{}".format(quote(repository_id, safe=""), quote(symbol_id, safe=""))
