"""
Pytest configuration and fixtures
"""
import os
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from app.main import app
from app.db.database import Base, get_db
from app.core.config import settings

# Override settings for testing
os.environ["TESTING"] = "1"


@pytest.fixture(scope="session")
def postgres_container():
    """Create PostgreSQL container for testing"""
    with PostgresContainer(
        image="postgres:15-alpine",
        user="postgres",
        password="test",
        dbname="test_db"
    ) as postgres:
        yield postgres


@pytest.fixture(scope="session")
def redis_container():
    """Create Redis container for testing"""
    with RedisContainer(image="redis:7-alpine") as redis:
        yield redis


@pytest.fixture(scope="session")
def test_db_url(postgres_container):
    """Get test database URL"""
    return postgres_container.get_connection_url()


@pytest.fixture(scope="function")
def test_db(test_db_url):
    """Create test database session"""
    # Ensure Celery tasks use the same test DB
    from app.core.config import settings as _settings
    psycopg_dsn = test_db_url.replace("postgresql+psycopg2://", "postgresql://")
    _settings.database_url = psycopg_dsn

    engine = create_engine(test_db_url)
    Base.metadata.create_all(bind=engine)
    
    # Create materialized views for analytics tests
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hires_q AS
            SELECT 
                department_id,
                job_id,
                date_trunc('quarter', hire_dt)::date AS quarter,
                COUNT(*) AS hires
            FROM hired_employees
            GROUP BY department_id, job_id, quarter;

            CREATE UNIQUE INDEX IF NOT EXISTS mv_hires_q_pk 
                ON mv_hires_q (department_id, job_id, quarter);
                
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_dept_mean AS
            WITH yearly_hires AS (
                SELECT 
                    department_id,
                    EXTRACT(YEAR FROM hire_dt) as year,
                    COUNT(*) AS hired
                FROM hired_employees
                GROUP BY department_id, year
            ),
            mean_by_year AS (
                SELECT 
                    year,
                    AVG(hired) as mean_hires
                FROM yearly_hires
                GROUP BY year
            )
            SELECT 
                d.id,
                d.department,
                yh.hired,
                yh.year,
                m.mean_hires
            FROM yearly_hires yh
            JOIN departments d ON yh.department_id = d.id
            JOIN mean_by_year m ON yh.year = m.year
            WHERE yh.hired > m.mean_hires;

            CREATE UNIQUE INDEX IF NOT EXISTS mv_dept_mean_pk 
                ON mv_dept_mean (id, year);
        """))
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Override the get_db dependency
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield TestingSessionLocal()
    
    # Cleanup materialized views first, then tables
    with engine.begin() as conn:
        conn.execute(text("DROP MATERIALIZED VIEW IF EXISTS mv_dept_mean CASCADE"))
        conn.execute(text("DROP MATERIALIZED VIEW IF EXISTS mv_hires_q CASCADE"))
    
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_db, test_db_url):
    """Create FastAPI test client with default API key header"""
    # Ensure Celery runs tasks eagerly during tests
    from app.workers.celery_app import celery_app
    celery_app.conf.task_always_eager = True

    # Point application settings to test database
    from app.core.config import settings as _settings
    psycopg_dsn = test_db_url.replace("postgresql+psycopg2://", "postgresql://")
    _settings.database_url = psycopg_dsn

    test_client = TestClient(app)
    test_client.headers.update({"X-API-Key": "local-dev-key"})
    return test_client


@pytest.fixture
def sample_csv_files(tmp_path):
    """Create sample CSV files for testing"""
    # Departments CSV
    departments_csv = tmp_path / "departments.csv"
    departments_csv.write_text(
        "id,department\n"
        "1,Supply Chain\n"
        "2,Maintenance\n"
        "3,Staff\n"
        "4,Engineering\n"
        "5,Marketing\n"
    )
    
    # Jobs CSV
    jobs_csv = tmp_path / "jobs.csv"
    jobs_csv.write_text(
        "id,job\n"
        "1,Recruiter\n"
        "2,Manager\n"
        "3,Analyst\n"
        "4,Engineer\n"
        "5,Designer\n"
    )
    
    # Hired employees CSV
    employees_csv = tmp_path / "hired_employees.csv"
    employees_csv.write_text(
        "id,name,datetime,department_id,job_id\n"
        "1,John Doe,2021-01-15T10:00:00Z,1,2\n"
        "2,Jane Smith,2021-02-20T14:30:00Z,2,3\n"
        "3,Bob Johnson,2021-03-10T09:15:00Z,3,1\n"
        "4,Alice Brown,2021-04-05T11:45:00Z,1,4\n"
        "5,Charlie Wilson,2021-05-12T13:20:00Z,4,2\n"
        "6,Diana Lee,2021-06-18T10:30:00Z,5,5\n"
        "7,Eve Martinez,2021-07-22T15:00:00Z,3,3\n"
        "8,Frank Garcia,2021-08-30T09:00:00Z,2,1\n"
        "9,Grace Kim,2021-09-14T12:00:00Z,4,4\n"
        "10,Henry Chen,2021-10-25T16:30:00Z,5,2\n"
    )
    
    return {
        "departments": departments_csv,
        "jobs": jobs_csv,
        "hired_employees": employees_csv
    }


@pytest.fixture
def batch_data():
    """Sample data for batch insert testing"""
    return {
        "departments": [
            {"id": 6, "department": "Finance"},
            {"id": 7, "department": "Legal"}
        ],
        "jobs": [
            {"id": 6, "job": "Accountant"},
            {"id": 7, "job": "Lawyer"}
        ],
        "hired_employees": [
            {
                "id": 11,
                "name": "Test User 1",
                "datetime": "2021-11-01T10:00:00Z",
                "department_id": 1,
                "job_id": 1
            },
            {
                "id": 12,
                "name": "Test User 2",
                "datetime": "2021-12-15T14:30:00Z",
                "department_id": 2,
                "job_id": 2
            }
        ]
    } 