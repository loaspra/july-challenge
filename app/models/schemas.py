"""
Pydantic schemas for API validation
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


# Department schemas
class DepartmentBase(BaseModel):
    id: int
    department: str


class DepartmentCreate(BaseModel):
    id: int
    department: str


class Department(DepartmentBase):
    class Config:
        from_attributes = True


# Job schemas
class JobBase(BaseModel):
    id: int
    job: str


class JobCreate(BaseModel):
    id: int
    job: str


class Job(JobBase):
    class Config:
        from_attributes = True


# Employee schemas
class HiredEmployeeBase(BaseModel):
    id: int
    name: str
    datetime: str  # ISO format string
    department_id: int
    job_id: int
    
    @field_validator('datetime')
    def validate_datetime(cls, v):
        """Validate ISO datetime format"""
        try:
            # Try parsing ISO format with Z
            if v.endswith('Z'):
                dt = datetime.fromisoformat(v[:-1] + '+00:00')
            else:
                dt = datetime.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid datetime format: {v}")


class HiredEmployeeCreate(HiredEmployeeBase):
    pass


class HiredEmployee(BaseModel):
    id: int
    name: str
    hire_dt: datetime
    department_id: int
    job_id: int
    hire_year: int
    department: Optional[Department] = None
    job: Optional[Job] = None
    
    class Config:
        from_attributes = True


# Batch insert schemas
class BatchInsertRequest(BaseModel):
    table: str = Field(..., pattern="^(departments|jobs|hired_employees)$")
    rows: List[Dict[str, Any]] = Field(..., min_items=1, max_items=1000)


class BatchInsertResponse(BaseModel):
    table: str
    rows_inserted: int
    duration_ms: float


# File upload response
class FileUploadResponse(BaseModel):
    task_id: str
    status: str
    message: str
    filename: str
    rows_to_process: Optional[int] = None


# Analytics schemas
class QuarterlyHiresRow(BaseModel):
    department: str
    job: str
    Q1: int = 0
    Q2: int = 0
    Q3: int = 0
    Q4: int = 0


class QuarterlyHiresResponse(BaseModel):
    year: int
    data: List[QuarterlyHiresRow]
    total_rows: int


class DepartmentAboveMeanRow(BaseModel):
    id: int
    department: str
    hired: int


class DepartmentAboveMeanResponse(BaseModel):
    year: int
    mean_hires: float
    data: List[DepartmentAboveMeanRow]
    total_departments: int


# Task status schema
class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: Optional[int] = None
    total: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None 