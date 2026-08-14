import importlib.util
from pathlib import Path
import pytest

SPEC=importlib.util.spec_from_file_location("run_retrieval",Path(__file__).parents[1]/"run_retrieval.py")
harness=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(harness)

def test_rank_metrics_and_aggregate():
    metrics=harness.rank_metrics([{"path":"no.py"},{"path":"a.py","symbol":"wanted"}],{"a.py"},{"wanted"})
    assert metrics["files"] == {"hit_at_1":0.0,"hit_at_5":1.0,"mrr":0.5}
    assert metrics["symbols"]["mrr"] == 0.5
    row={"mode":"text","status":"ok","metrics":metrics,"latency_ms":10}
    summary=harness.aggregate([row])
    assert summary["text"]["files"]["hit_at_5"] == 1.0
    assert summary["semantic"]["status"] == "unavailable"

def test_task_digest_changes_with_content(tmp_path):
    task={"id":"x","_source":"a.json","_content_sha256":"one"}
    assert harness.task_digest([task]) != harness.task_digest([{**task,"_content_sha256":"two"}])

def test_snapshot_mismatch_is_fatal(monkeypatch):
    corpus={"active_workspace":"x","corpora":[{"id":"x","members":[{"id":"repo","source_url":"https://example/repo.git","resolved_sha":"abc"}]}]}
    monkeypatch.setattr(harness,"request",lambda *args: ([{"id":"1","name":"repo","clone_url":"https://example/repo.git","indexed_commit_sha":"wrong"}],0))
    with pytest.raises(harness.HarnessError,match="snapshot mismatch"):
        harness.capture_manifest("http://test",corpus,1)

def test_unexpected_request_failure_is_fatal(monkeypatch):
    monkeypatch.setattr(
        harness, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("dead"))
    )
    with pytest.raises(harness.HarnessError, match="connection error"):
        harness.request("http://test", "/api/search", 1)


def test_aggregate_rejects_partial_supported_mode():
    rows = [
        {"mode": "text", "status": "ok", "metrics": harness.rank_metrics([], set(), set()), "latency_ms": 1},
        {"mode": "text", "status": "unavailable", "reason": "broken"},
    ]
    with pytest.raises(harness.HarnessError, match="incomplete text coverage"):
        harness.aggregate(rows)
