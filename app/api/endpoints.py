"""
API endpoints for the Globant Challenge
"""
import os
import tempfile
import time
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd
import io

from app.db.database import get_db
from app.models import schemas
from app.workers.tasks import process_csv_upload
from app.workers.celery_app import celery_app
from app.core.config import settings
from app.core.security import get_api_key

router = APIRouter()


# Health check endpoint
@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Check database connection
        db.execute(text("SELECT 1"))
        
        # Check Redis connection
        celery_app.backend.get("health_check")
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "redis": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


# CSV Upload endpoint
@router.post("/upload/csv/{table}", response_model=schemas.FileUploadResponse)
async def upload_csv(
    table: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """
    Upload CSV file for processing
    Supports: departments, jobs, hired_employees
    """
    # Validate table name
    if table not in ["departments", "jobs", "hired_employees"]:
        raise HTTPException(status_code=400, detail=f"Invalid table name: {table}")
    
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    
    # Check file size (skip for in-memory files in tests)
    if file.size is not None and file.size > settings.max_upload_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.max_upload_size / 1024 / 1024:.0f} MB"
        )
    
    try:
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            temp_path = tmp_file.name
        
        # Quick validation with pandas
        try:
            df = pd.read_csv(temp_path, nrows=10)
            expected_columns = {
                'departments': ['id', 'department'],
                'jobs': ['id', 'job'],
                'hired_employees': ['id', 'name', 'datetime', 'department_id', 'job_id']
            }
            
            if list(df.columns) != expected_columns.get(table, []):
                os.unlink(temp_path)
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid CSV structure for {table}. Expected columns: {expected_columns[table]}"
                )
            
            row_count = sum(1 for _ in open(temp_path)) - 1
        except HTTPException:
            # Re-raise HTTPExceptions (they already have the right status code)
            raise
        except Exception as e:
            os.unlink(temp_path)
            raise HTTPException(status_code=400, detail=f"Invalid CSV file: {str(e)}")
        
        # Submit to Celery for processing
        task = process_csv_upload.delay(temp_path, table)
        
        return schemas.FileUploadResponse(
            task_id=task.id,
            status="accepted",
            message=f"File uploaded successfully. Processing {row_count} rows...",
            filename=file.filename,
            rows_to_process=row_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# Batch insert endpoint
@router.post("/batch/{table}", response_model=schemas.BatchInsertResponse)
async def batch_insert(
    table: str,
    request: schemas.BatchInsertRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """
    Insert batch of rows (1-1000) into specified table
    """
    start_time = time.time()
    
    # Validate table name matches request
    if table != request.table:
        raise HTTPException(
            status_code=400,
            detail=f"Table mismatch: URL has '{table}', body has '{request.table}'"
        )
    
    try:
        if table == "departments":
            # Validate and insert departments
            for row in request.rows:
                dept = schemas.DepartmentCreate(**row)
                db.execute(
                    text("INSERT INTO departments (id, department) VALUES (:id, :department) ON CONFLICT (id) DO NOTHING"),
                    {"id": dept.id, "department": dept.department}
                )
        
        elif table == "jobs":
            # Validate and insert jobs
            for row in request.rows:
                job = schemas.JobCreate(**row)
                db.execute(
                    text("INSERT INTO jobs (id, job) VALUES (:id, :job) ON CONFLICT (id) DO NOTHING"),
                    {"id": job.id, "job": job.job}
                )
        
        elif table == "hired_employees":
            # Validate and insert hired employees
            for row in request.rows:
                emp = schemas.HiredEmployeeCreate(**row)
                # Calculate hire_year from datetime
                hire_year = emp.datetime.year
                db.execute(
                    text("INSERT INTO hired_employees (id, name, hire_dt, hire_year, department_id, job_id) VALUES (:id, :name, :hire_dt, :hire_year, :department_id, :job_id) ON CONFLICT (id) DO NOTHING"),
                    {"id": emp.id, "name": emp.name, "hire_dt": emp.datetime, "hire_year": hire_year, "department_id": emp.department_id, "job_id": emp.job_id}
                )
        else:
            raise HTTPException(status_code=400, detail=f"Invalid table: {table}")
        
        db.commit()
        duration_ms = (time.time() - start_time) * 1000
        
        return schemas.BatchInsertResponse(
            table=table,
            rows_inserted=len(request.rows),
            duration_ms=duration_ms
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Batch insert failed: {str(e)}")


# Task status endpoint
@router.get("/task/{task_id}", response_model=schemas.TaskStatus)
async def get_task_status(task_id: str, api_key: str = Depends(get_api_key)):
    """Get status of async task"""
    try:
        task = celery_app.AsyncResult(task_id)
        
        if task.state == 'PENDING':
            return schemas.TaskStatus(
                task_id=task_id,
                status='pending',
                progress=0,
                total=0
            )
        elif task.state == 'PROCESSING':
            meta = task.info
            return schemas.TaskStatus(
                task_id=task_id,
                status='processing',
                progress=meta.get('progress', 0),
                total=meta.get('total', 0)
            )
        elif task.state == 'SUCCESS':
            return schemas.TaskStatus(
                task_id=task_id,
                status='completed',
                result=task.result
            )
        else:  # FAILURE
            return schemas.TaskStatus(
                task_id=task_id,
                status='failed',
                error=str(task.info)
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking task status: {str(e)}")


# Analytics endpoint - Quarterly hires
@router.get("/analytics/hired/by-quarter", response_model=schemas.QuarterlyHiresResponse)
async def get_quarterly_hires(
    year: int = Query(default=2021, ge=2000, le=2030),
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """
    Get number of employees hired for each job and department in specified year divided by quarter
    """
    try:
        # Query the materialized view
        result = db.execute(
            text("""
                SELECT 
                    d.department,
                    j.job,
                    EXTRACT(QUARTER FROM h.quarter) as quarter,
                    h.hires
                FROM mv_hires_q h
                JOIN departments d ON h.department_id = d.id
                JOIN jobs j ON h.job_id = j.id
                WHERE EXTRACT(YEAR FROM h.quarter) = :year
                ORDER BY d.department, j.job
            """),
            {"year": year}
        )
        
        # Transform to desired format
        rows_dict = {}
        for row in result:
            key = (row.department, row.job)
            if key not in rows_dict:
                rows_dict[key] = {
                    "department": row.department,
                    "job": row.job,
                    "Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0
                }
            rows_dict[key][f"Q{int(row.quarter)}"] = row.hires
        
        data = [schemas.QuarterlyHiresRow(**row) for row in rows_dict.values()]
        
        return schemas.QuarterlyHiresResponse(
            year=year,
            data=data,
            total_rows=len(data)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics query failed: {str(e)}")


# Analytics endpoint - Departments above average
@router.get("/analytics/departments/above-average", response_model=schemas.DepartmentAboveMeanResponse)
async def get_departments_above_average(
    year: int = Query(default=2021, ge=2000, le=2030),
    format: str = Query(default="json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """
    List departments that hired more employees than the mean of employees hired in specified year
    """
    try:
        # Query with CTE for clarity
        result = db.execute(
            text("""
                WITH yearly_hires AS (
                    SELECT 
                        department_id,
                        COUNT(*) as hired
                    FROM hired_employees
                    WHERE EXTRACT(YEAR FROM hire_dt) = :year
                    GROUP BY department_id
                ),
                mean_calc AS (
                    SELECT AVG(hired)::float as mean_hires
                    FROM yearly_hires
                )
                SELECT 
                    d.id,
                    d.department,
                    yh.hired,
                    mc.mean_hires
                FROM yearly_hires yh
                JOIN departments d ON yh.department_id = d.id
                CROSS JOIN mean_calc mc
                WHERE yh.hired > mc.mean_hires
                ORDER BY yh.hired DESC
            """),
            {"year": year}
        )
        
        rows = result.fetchall()
        mean_hires = rows[0].mean_hires if rows else 0.0
        
        data = [
            schemas.DepartmentAboveMeanRow(
                id=row.id,
                department=row.department,
                hired=row.hired
            )
            for row in rows
        ]
        
        if format == "csv":
            # Return CSV format
            output = io.StringIO()
            output.write("id,department,hired\n")
            for row in data:
                output.write(f"{row.id},{row.department},{row.hired}\n")
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=departments_above_average_{year}.csv"}
            )
        
        return schemas.DepartmentAboveMeanResponse(
            year=year,
            mean_hires=mean_hires,
            data=data,
            total_departments=len(data)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics query failed: {str(e)}") 