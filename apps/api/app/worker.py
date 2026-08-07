from redis import Redis
from rq import Worker, Queue
from app.config import settings
if __name__=='__main__': Worker([Queue('indexing',connection=Redis.from_url(settings.redis_url))],connection=Redis.from_url(settings.redis_url)).work()
