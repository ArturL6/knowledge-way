from types import SimpleNamespace
from app.search import parse_query, query_terms, result


def test_sourcegraph_filter_parser():
    query = parse_query('repo:backend lang:python path:src/auth "refresh token"')
    assert (query.repo, query.language, query.path, query.text) == (
        "backend", "python", "src/auth", "refresh token"
    )


def test_query_terms_keep_code_identifiers_and_drop_question_words():
    assert query_terms("Where is get_dependant defined?") == ["get_dependant"]


def test_result_exposes_symbol_and_indexed_commit_metadata():
    repo = SimpleNamespace(id="repo", name="demo")
    file = SimpleNamespace(id="file", path="demo.py", indexed_commit_sha="commit")
    symbol = SimpleNamespace(id="symbol", language="python", start_line=1, end_line=2, source_text="def f(): pass", qualified_name="demo.f")
    chunk = SimpleNamespace(symbol_id="symbol", language="python", start_line=1, end_line=2, source_text="def f(): pass", qualified_symbol_name="demo.f", indexed_commit_sha="chunk-commit")
    assert result("symbol", 1, repo, file, symbol)["symbol_id"] == "symbol"
    chunk_result = result("chunk", 1, repo, file, chunk)
    assert (chunk_result["symbol_id"], chunk_result["indexed_commit_sha"]) == ("symbol", "chunk-commit")
