"""Database setup. Portable: PostgreSQL (JSONB) or SQLite (JSON) via DATABASE_URL."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Default: local PostgreSQL (portable install). Override with DATABASE_URL for SQLite fallback:
#   DATABASE_URL=sqlite:///bathroom.db
DEFAULT_URL = "postgresql+psycopg2://bathroom:bathroom@127.0.0.1:5432/bathroom_designer"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_URL)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
