"""
Database connection and session management
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Create SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    poolclass=NullPool,  # Let pgbouncer handle connection pooling
    echo=False,
    future=True
)

# Create session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# Create declarative base
Base = declarative_base()

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database with required extensions"""
    with engine.begin() as conn:
        # Create extensions
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_partman CASCADE;"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_cron;"))
        
        # Create schema for partman
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS partman;"))
        
        # Grant permissions
        conn.execute(text("GRANT ALL ON SCHEMA partman TO postgres;"))
        conn.execute(text("GRANT ALL ON ALL TABLES IN SCHEMA partman TO postgres;"))
        conn.execute(text("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA partman TO postgres;"))
        conn.execute(text("GRANT EXECUTE ON ALL PROCEDURES IN SCHEMA partman TO postgres;")) 