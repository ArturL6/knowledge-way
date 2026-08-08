from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
class Base(DeclarativeBase): pass

def verify_migration_ready():
    """Fail fast when the database was not upgraded to this application's head."""
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    expected_heads = set(ScriptDirectory.from_config(config).get_heads())
    with engine.connect() as connection:
        current_heads = set(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
    if current_heads != expected_heads:
        raise RuntimeError(
            "Database migrations are not current. Run `alembic -c alembic.ini upgrade head`."
        )

def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()
