"""
Celery tasks for CSV processing
"""
import io
import os
import tempfile
import time
from datetime import datetime
from typing import Dict, Any, List
from celery import Task
from celery.utils.log import get_task_logger
import pandas as pd
import pyarrow as pa
import pyarrow.csv as csv
import psycopg
from psycopg import sql

from app.workers.celery_app import celery_app
from app.core.config import settings
from app.models.schemas import HiredEmployeeBase, DepartmentCreate, JobCreate

logger = get_task_logger(__name__)


class CSVProcessTask(Task):
    """Base task with database connection management"""
    _conn = None
    
    @property
    def conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(settings.database_url)
        return self._conn
    
    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        if self._conn and not self._conn.closed:
            self._conn.close()


@celery_app.task(
    bind=True,
    base=CSVProcessTask,
    name='process_csv_upload',
    max_retries=3,
    default_retry_delay=60
)
def process_csv_upload(self, file_path: str, table_name: str) -> Dict[str, Any]:
    """
    Process CSV file upload using PostgreSQL COPY for efficiency
    """
    start_time = time.time()
    rows_processed = 0
    
    try:
        # Update task state
        self.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'total': 0, 'message': 'Starting CSV processing...'}
        )
        
        # Validate table name
        if table_name not in ['departments', 'jobs', 'hired_employees']:
            raise ValueError(f"Invalid table name: {table_name}")
        
        # Get row count for progress tracking
        with open(file_path, 'r') as f:
            total_rows = sum(1 for line in f) - 1  # Subtract header
        
        # Configure COPY based on table
        if table_name == 'hired_employees':
            # Process hired_employees with date transformation
            rows_processed = _process_hired_employees(
                self, file_path, total_rows
            )
        else:
            # Process departments or jobs (simpler structure)
            rows_processed = _process_simple_table(
                self, file_path, table_name, total_rows
            )
        
        # Refresh materialized views if needed
        if table_name == 'hired_employees':
            _refresh_materialized_views(self.conn)
        
        duration = time.time() - start_time
        
        return {
            'status': 'completed',
            'table': table_name,
            'rows_processed': rows_processed,
            'duration_seconds': duration,
            'throughput_rows_per_sec': rows_processed / duration if duration > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error processing CSV: {str(e)}")
        self.retry(exc=e)
    finally:
        # Clean up temp file
        if os.path.exists(file_path):
            os.unlink(file_path)


def _process_hired_employees(task, file_path: str, total_rows: int) -> int:
    """Process hired_employees table with date transformation and partitioning"""
    conn = task.conn
    rows_processed = 0
    chunk_size = settings.batch_size
    
    # Create temp table for staging
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TEMP TABLE temp_hired_employees (
                id INTEGER,
                name TEXT,
                datetime_str TEXT,
                department_id INTEGER,
                job_id INTEGER
            )
        """)
        
        # Disable indexes for faster loading
        cur.execute("SET synchronous_commit = off")
        cur.execute("SET client_min_messages = warning")
        
        # Process in chunks
        for chunk_num, chunk in enumerate(pd.read_csv(
            file_path,
            chunksize=chunk_size,
            header=0,
            names=['id', 'name', 'datetime', 'department_id', 'job_id']
        )):
            # Update progress
            task.update_state(
                state='PROCESSING',
                meta={
                    'progress': rows_processed,
                    'total': total_rows,
                    'message': f'Processing chunk {chunk_num + 1}...'
                }
            )
            
            # Write chunk to temp CSV
            temp_csv = io.StringIO()
            chunk.to_csv(temp_csv, index=False, header=False)
            temp_csv.seek(0)
            
            # COPY to temp table
            with cur.copy(
                "COPY temp_hired_employees FROM STDIN WITH CSV"
            ) as copy:
                copy.write(temp_csv.getvalue())
            
            rows_processed += len(chunk)
        
        # Insert from temp table with date conversion
        cur.execute("""
            INSERT INTO hired_employees (id, name, hire_dt, hire_year, department_id, job_id)
            SELECT 
                id,
                name,
                CASE 
                    WHEN datetime_str LIKE '%Z' THEN 
                        (substring(datetime_str, 1, length(datetime_str)-1) || '+00:00')::timestamp with time zone
                    ELSE 
                        datetime_str::timestamp with time zone
                END as hire_dt,
                EXTRACT(YEAR FROM 
                    CASE 
                        WHEN datetime_str LIKE '%Z' THEN 
                            (substring(datetime_str, 1, length(datetime_str)-1) || '+00:00')::timestamp with time zone
                        ELSE 
                            datetime_str::timestamp with time zone
                    END
                )::int as hire_year,
                department_id,
                job_id
            FROM temp_hired_employees
            ON CONFLICT (id) DO NOTHING
        """)
        
        # Run ANALYZE for query optimization
        cur.execute("ANALYZE hired_employees")
        
        conn.commit()
    
    return rows_processed


def _process_simple_table(task, file_path: str, table_name: str, total_rows: int) -> int:
    """Process departments or jobs tables"""
    conn = task.conn
    rows_processed = 0
    
    with conn.cursor() as cur:
        # Disable indexes for faster loading
        cur.execute("SET synchronous_commit = off")
        
        with open(file_path, 'r') as f:
            # Skip header
            next(f)
            
            # Use COPY for bulk loading
            with cur.copy(
                sql.SQL("COPY {} FROM STDIN WITH CSV").format(
                    sql.Identifier(table_name)
                )
            ) as copy:
                for line in f:
                    copy.write(line)
                    rows_processed += 1
                    
                    # Update progress every 1000 rows
                    if rows_processed % 1000 == 0:
                        task.update_state(
                            state='PROCESSING',
                            meta={
                                'progress': rows_processed,
                                'total': total_rows,
                                'message': f'Loaded {rows_processed} rows...'
                            }
                        )
        
        # Run ANALYZE
        cur.execute(sql.SQL("ANALYZE {}").format(sql.Identifier(table_name)))
        conn.commit()
    
    return rows_processed


def _refresh_materialized_views(conn):
    """Refresh materialized views after data load"""
    with conn.cursor() as cur:
        logger.info("Refreshing materialized views...")
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY IF EXISTS mv_hires_q")
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY IF EXISTS mv_dept_mean")
        conn.commit()


@celery_app.task(name='setup_partitions')
def setup_partitions(start_year: int = 2020, end_year: int = 2025):
    """Setup partitions for hired_employees table"""
    try:
        conn = psycopg.connect(settings.database_url)
        with conn.cursor() as cur:
            # Create partitions for each year
            for year in range(start_year, end_year + 1):
                partition_name = f"hired_employees_{year}"
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {partition_name} 
                    PARTITION OF hired_employees 
                    FOR VALUES FROM ({year}) TO ({year + 1})
                """)
                logger.info(f"Created partition: {partition_name}")
            
            conn.commit()
        conn.close()
        return {'status': 'success', 'partitions_created': end_year - start_year + 1}
    except Exception as e:
        logger.error(f"Error setting up partitions: {str(e)}")
        raise 