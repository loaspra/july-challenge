"""
SQLAlchemy models for the application
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from app.db.database import Base


class Department(Base):
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True)
    department = Column(String, nullable=False)
    
    # Relationship
    employees = relationship("HiredEmployee", back_populates="department")
    
    def __repr__(self):
        return f"<Department(id={self.id}, name={self.department})>"


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True)
    job = Column(String, nullable=False)
    
    # Relationship
    employees = relationship("HiredEmployee", back_populates="job")
    
    def __repr__(self):
        return f"<Job(id={self.id}, name={self.job})>"


class HiredEmployee(Base):
    __tablename__ = "hired_employees"
    
    # Primary key 
    id = Column(Integer, primary_key=True)
    hire_year = Column(Integer, nullable=False, index=True)
    
    # Employee data
    name = Column(String, nullable=False)
    hire_dt = Column(DateTime, nullable=False, index=True)
    
    # Foreign keys
    department_id = Column(Integer, ForeignKey("departments.id"), index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), index=True)
    
    # Relationships
    department = relationship("Department", back_populates="employees")
    job = relationship("Job", back_populates="employees")
    
    # Indexes for analytics queries
    __table_args__ = (
        Index('idx_hired_employees_dept_job_date', 'department_id', 'job_id', 'hire_dt'),
        Index('idx_hired_employees_year_dept', 'hire_year', 'department_id'),
        # Note: Partitioning removed temporarily to get tests working
    )
    
    @hybrid_property
    def quarter(self):
        """Get quarter from hire date"""
        return (self.hire_dt.month - 1) // 3 + 1
    
    def __repr__(self):
        return f"<HiredEmployee(id={self.id}, name={self.name}, hired={self.hire_dt})>" 