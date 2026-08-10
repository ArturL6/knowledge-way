"""Reconciles indexing job rows whose work-horse died without unwinding.

A job killed by RQ's timeout (or any SIGKILL) never reaches the `except` block in
`app.ingestion.index_repository`, so nothing writes `failed`. RQ cannot help here either: for a
killed work-horse it calls `Worker.handle_job_failure` directly, which bypasses `on_failure`
callbacks. Without this reconciliation the repository stays `indexing` forever and the UI polls a
status that will never change.
"""

from datetime import datetime, timedelta

from redis import Redis
from rq import Worker
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import IndexingJob, Repository

# A worker registers itself before it reports a current job, so ignore rows that just started.
ORPHAN_GRACE = timedelta(seconds=60)
ORPHAN_MESSAGE = 'Indexing stopped unexpectedly. The worker exited or the job exceeded its timeout.'


def _repository_ids_being_indexed() -> set[str]:
    """Repository ids that some live RQ worker is currently indexing."""
    connection = Redis.from_url(settings.redis_url)
    active = set()
    for worker in Worker.all(connection=connection):
        job = worker.get_current_job()
        if job is not None and job.args:
            active.add(str(job.args[0]))
    return active


def reconcile_indexing_jobs(db: Session) -> int:
    """Fails job rows left `running` with no worker behind them. Returns the number reclaimed.

    Never raises: reconciliation is opportunistic and must not break the request that triggered it.
    """
    try:
        running = db.scalars(select(IndexingJob).where(IndexingJob.status == 'running')).all()
        if not running:
            return 0
        cutoff = datetime.utcnow() - ORPHAN_GRACE
        candidates = [job for job in running if job.started_at is None or job.started_at < cutoff]
        if not candidates:
            return 0
        active = _repository_ids_being_indexed()
        orphaned = [job for job in candidates if job.repository_id not in active]
        for job in orphaned:
            job.status = 'failed'
            job.finished_at = datetime.utcnow()
            job.error_message = job.error_message or ORPHAN_MESSAGE
            repository = db.get(Repository, job.repository_id)
            if repository is not None and repository.indexing_status == 'indexing':
                repository.indexing_status = 'failed'
                repository.error_message = job.error_message
        if orphaned:
            db.commit()
        return len(orphaned)
    except Exception:
        db.rollback()
        return 0
