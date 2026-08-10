from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """Tests build their own throwaway SQLite engines; SQLite defaults FK
    enforcement to OFF per-connection, which made every `ondelete='CASCADE'`
    in app/models.py inert under test. Listening on the Engine class (not an
    instance) catches every engine any test creates, wherever it's created."""
    if type(dbapi_connection).__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
