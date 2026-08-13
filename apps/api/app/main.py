"""Application composition root.

Inbound HTTP routes and outbound adapters are wired here; request handling lives in
``adapters.inbound.http.routes``.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.inbound.http.dependencies import SessionLocal, reconcile_indexing_jobs, settings, verify_migration_ready
from app.adapters.inbound.http.routes import router

app = FastAPI(title="knowledge-way API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    verify_migration_ready()
    db = SessionLocal()
    try:
        reconcile_indexing_jobs(db)
    finally:
        db.close()


app.include_router(router)
