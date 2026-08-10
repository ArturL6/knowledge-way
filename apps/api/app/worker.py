from redis import Redis
from rq import Worker, Queue
from app.config import settings
from app.db import SessionLocal, engine
from app.reconcile import reconcile_indexing_jobs


class ForkSafeWorker(Worker):
 """Drops the connection pool inherited through RQ's fork before the job runs."""

 def main_work_horse(self, job, queue):
  # The child inherits the parent's pooled sockets. Reusing one interleaves two processes on
  # a single connection, which is how a job left an `idle in transaction` session holding
  # RowExclusiveLock on symbols, code_chunks and symbol_edges. close=False detaches them
  # without closing the file descriptors the parent still owns.
  engine.dispose(close=False)
  return super().main_work_horse(job, queue)


if __name__=='__main__':
 # A restarted worker cannot resume the jobs its predecessor lost, so fail their rows first.
 db=SessionLocal()
 try: reconcile_indexing_jobs(db)
 finally: db.close()
 ForkSafeWorker([Queue('indexing',connection=Redis.from_url(settings.redis_url))],connection=Redis.from_url(settings.redis_url)).work()
