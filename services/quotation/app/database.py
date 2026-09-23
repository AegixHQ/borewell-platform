import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://borewell:borewell@localhost:5432/quotation",
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Pool settings explicit and env-tunable, not left as SQLAlchemy's
# unexamined defaults (pool_size=5, max_overflow=10 - which happen to be
# reasonable at this service's actual scale: a single-contractor pilot,
# per Architecture doc section 10, not a value anyone had actually
# reasoned about before this). SQLite ignores pool_size/max_overflow
# entirely (single-file, no real connection pool), so these only take
# effect against real Postgres - safe to always pass.
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    # Recycle connections older than 30 min - guards against Postgres or
    # an intermediate load balancer silently dropping a long-idle
    # connection, which would otherwise surface as a confusing
    # "connection already closed" error on the next request to use it,
    # not at connect time.
    pool_recycle=1800,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
