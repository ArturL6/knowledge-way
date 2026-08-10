from redis import Redis
from rq import Worker, Queue
from app.config import settings
from app.db import SessionLocal
from app.reconcile import reconcile_indexing_jobs

if __name__=='__main__':
 # A restarted worker cannot resume the jobs its predecessor lost, so fail their rows first.
 db=SessionLocal()
 try: reconcile_indexing_jobs(db)
 finally: db.close()
 Worker([Queue('indexing',connection=Redis.from_url(settings.redis_url))],connection=Redis.from_url(settings.redis_url)).work()
