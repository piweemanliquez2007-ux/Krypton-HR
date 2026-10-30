from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.errors import translate_db_error

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """FastAPI dependency: gives each request its own DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def transaction(db: Session):
    """
    Used by SERVICES around any write:

        with transaction(db):
            employee_repository.insert(db, data)

    Commits if the block succeeds. If it fails, rolls back and converts the database
    error into one of our AppErrors (so it becomes a clean 400/409, not a 500 crash).
    """
    try:
        yield
        db.commit()
    except DBAPIError as exc:
        db.rollback()
        raise translate_db_error(exc) from exc
    except Exception:
        db.rollback()
        raise
