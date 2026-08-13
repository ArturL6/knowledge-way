from app.application.ports import (
    CodeParser,
    Embeddings,
    JobQueue,
    LLM,
    LexicalSearch,
    RepoStore,
    SourceControl,
    VectorSearch,
)


def test_hexagonal_port_contracts_are_runtime_checkable():
    """The R.4 ports are available to use cases without adapter imports."""
    expected = {
        "RepoStore": RepoStore,
        "SourceControl": SourceControl,
        "LexicalSearch": LexicalSearch,
        "VectorSearch": VectorSearch,
        "CodeParser": CodeParser,
        "LLM": LLM,
        "Embeddings": Embeddings,
        "JobQueue": JobQueue,
    }
    assert len(expected) == 8
    assert all(getattr(port, "_is_runtime_protocol", False) for port in expected.values())