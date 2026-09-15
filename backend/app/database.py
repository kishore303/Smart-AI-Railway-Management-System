from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

from app.core.config import settings

# SQLAlchemy Base for all models
Base = declarative_base()

# Sync engine — psycopg2, NullPool is safer for scripts; production can use QueuePool
engine = create_engine(
    settings.database_url,
    poolclass=NullPool,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_engine():
    return engine
