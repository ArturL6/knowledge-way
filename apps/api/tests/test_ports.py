from pathlib import Path

from app.application.fakes import (
    InMemoryCodeParser,
    InMemoryEmbeddings,
    InMemoryJobQueue,
    InMemoryLLM,
    InMemoryLexicalSearch,
    InMemoryRepoStore,
    InMemorySourceControl,
    InMemoryVectorSearch,
)
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


def test_in_memory_port_fakes_satisfy_contracts_without_adapters_or_docker(tmp_path):
    """Use-case dependencies are executable against all eight ports in memory."""
    repo_store = InMemoryRepoStore()
    source_control = InMemorySourceControl()
    lexical = InMemoryLexicalSearch(["lexical-result"])
    vector = InMemoryVectorSearch(["vector-result"])
    parser = InMemoryCodeParser()
    llm = InMemoryLLM({"answer": "in-memory"})
    embeddings = InMemoryEmbeddings()
    jobs = InMemoryJobQueue()

    assert isinstance(repo_store, RepoStore)
    assert isinstance(source_control, SourceControl)
    assert isinstance(lexical, LexicalSearch)
    assert isinstance(vector, VectorSearch)
    assert isinstance(parser, CodeParser)
    assert isinstance(llm, LLM)
    assert isinstance(embeddings, Embeddings)
    assert isinstance(jobs, JobQueue)

    repo_store.save({"id": "repo", "name": "Repository"})
    entity = repo_store.get_repository("repo")
    assert entity == {"id": "repo", "name": "Repository"}
    assert source_control.clone("https://example.test/repo.git", tmp_path, "abc") == "abc"
    assert lexical.search("symbol") == ["lexical-result"]
    assert vector.search([0.1]) == ["vector-result"]
    assert parser.analyze("def run(): pass", "python")["language"] == "python"
    assert llm.complete("summarize") == {"answer": "in-memory"}
    assert embeddings.embed(["one", "three"]) == [[3.0], [5.0]]
    assert jobs.enqueue("index", "repo") == ("index", ("repo",), {})
