"""RQ runs each job in a fork of the worker. The child inherits the parent's SQLAlchemy pool,
and two processes sharing one connection is how a job left an `idle in transaction` session
holding RowExclusiveLock on symbols, code_chunks and symbol_edges (REV-501)."""
from app import worker


def test_work_horse_drops_the_inherited_pool_before_running_the_job(monkeypatch):
    calls = []

    monkeypatch.setattr(worker.engine, "dispose", lambda close=True: calls.append(("dispose", close)))
    monkeypatch.setattr(
        worker.Worker, "main_work_horse", lambda self, job, queue: calls.append(("job", job))
    )

    worker.ForkSafeWorker.main_work_horse(object.__new__(worker.ForkSafeWorker), "job-1", "queue-1")

    # Order matters: disposing after the job has opened a connection defeats the purpose.
    # close=False matters too: closing would shut sockets the parent process still owns.
    assert calls == [("dispose", False), ("job", "job-1")]
