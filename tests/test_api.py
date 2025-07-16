"""
Tests for API endpoints
"""
import pytest
import io
from fastapi import status
from sqlalchemy import text


class TestHealthEndpoint:
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["database"] == "connected"


class TestBatchInsertEndpoint:
    def test_batch_insert_departments(self, client, batch_data):
        """Test batch insert for departments"""
        response = client.post(
            "/api/v1/batch/departments",
            json={"table": "departments", "rows": batch_data["departments"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["table"] == "departments"
        assert data["rows_inserted"] == 2
        assert "duration_ms" in data
    
    def test_batch_insert_validation_error(self, client):
        """Test batch insert with invalid data"""
        response = client.post(
            "/api/v1/batch/departments",
            json={"table": "departments", "rows": [{"invalid": "data"}]}
        )
        assert response.status_code == 400
    
    def test_batch_insert_over_limit(self, client):
        """Test batch insert with more than 1000 rows"""
        rows = [{"id": i, "department": f"Dept{i}"} for i in range(1001)]
        response = client.post(
            "/api/v1/batch/departments",
            json={"table": "departments", "rows": rows}
        )
        assert response.status_code == 422  # Validation error
    
    def test_batch_insert_empty_rows(self, client):
        """Test batch insert with empty rows"""
        response = client.post(
            "/api/v1/batch/departments",
            json={"table": "departments", "rows": []}
        )
        assert response.status_code == 422  # Validation error


class TestCSVUploadEndpoint:
    def test_upload_departments_csv(self, client, sample_csv_files):
        """Test CSV upload for departments"""
        with open(sample_csv_files["departments"], "rb") as f:
            response = client.post(
                "/api/v1/upload/csv/departments",
                files={"file": ("departments.csv", f, "text/csv")}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert "task_id" in data
        assert data["filename"] == "departments.csv"
        assert data["rows_to_process"] == 5
    
    def test_upload_invalid_table(self, client, sample_csv_files):
        """Test CSV upload with invalid table name"""
        with open(sample_csv_files["departments"], "rb") as f:
            response = client.post(
                "/api/v1/upload/csv/invalid_table",
                files={"file": ("departments.csv", f, "text/csv")}
            )
        
        assert response.status_code == 400
        assert "Invalid table name" in response.json()["detail"]
    
    def test_upload_non_csv_file(self, client):
        """Test upload of non-CSV file"""
        content = b"This is not a CSV file"
        response = client.post(
            "/api/v1/upload/csv/departments",
            files={"file": ("test.txt", io.BytesIO(content), "text/plain")}
        )
        
        assert response.status_code == 400
        assert "Only CSV files are supported" in response.json()["detail"]
    
    def test_upload_malformed_csv(self, client):
        """Test upload of malformed CSV"""
        content = b"invalid,csv,structure\nwithout,proper,headers"
        response = client.post(
            "/api/v1/upload/csv/departments",
            files={"file": ("bad.csv", io.BytesIO(content), "text/csv")}
        )
        
        assert response.status_code == 400
        assert "Invalid CSV structure" in response.json()["detail"]


class TestAnalyticsEndpoints:
    def test_quarterly_hires_no_data(self, client):
        """Test quarterly hires with no data"""
        response = client.get("/api/v1/analytics/hired/by-quarter?year=2021")
        assert response.status_code == 200
        data = response.json()
        assert data["year"] == 2021
        assert data["data"] == []
        assert data["total_rows"] == 0
    
    def test_quarterly_hires_with_data(self, client, test_db):
        """Test quarterly hires with sample data"""
        # Insert test data
        test_db.execute(
            text("""
            INSERT INTO departments (id, department) VALUES
            (1, 'Engineering'), (2, 'Sales');
            
            INSERT INTO jobs (id, job) VALUES
            (1, 'Engineer'), (2, 'Manager');
            
            INSERT INTO hired_employees (id, name, hire_dt, hire_year, department_id, job_id) VALUES
            (1, 'John Doe', '2021-01-15 10:00:00+00', EXTRACT(YEAR FROM '2021-01-15 10:00:00+00'::timestamp), 1, 1),
            (2, 'Jane Smith', '2021-01-20 10:00:00+00', EXTRACT(YEAR FROM '2021-01-20 10:00:00+00'::timestamp), 1, 1),
            (3, 'Bob Johnson', '2021-04-10 10:00:00+00', EXTRACT(YEAR FROM '2021-04-10 10:00:00+00'::timestamp), 2, 2);
            """)
        )
        test_db.commit()
        
        # Refresh materialized view to include new data
        test_db.execute(text("REFRESH MATERIALIZED VIEW mv_hires_q"))
        test_db.commit()
        
        response = client.get("/api/v1/analytics/hired/by-quarter?year=2021")
        assert response.status_code == 200
        data = response.json()
        assert data["year"] == 2021
        assert len(data["data"]) == 2
        
        # Check Q1 data for Engineering/Engineer
        eng_data = next(d for d in data["data"] if d["department"] == "Engineering")
        assert eng_data["Q1"] == 2
        assert eng_data["Q2"] == 0
    
    def test_departments_above_average(self, client, test_db):
        """Test departments above average endpoint"""
        # Insert test data
        test_db.execute(
            text("""
            INSERT INTO departments (id, department) VALUES
            (1, 'Engineering'), (2, 'Sales'), (3, 'HR');
            
            INSERT INTO jobs (id, job) VALUES (1, 'Engineer');
            
            INSERT INTO hired_employees (id, name, hire_dt, hire_year, department_id, job_id) VALUES
            (1, 'E1', '2021-01-15 10:00:00+00', EXTRACT(YEAR FROM '2021-01-15 10:00:00+00'::timestamp), 1, 1),
            (2, 'E2', '2021-01-20 10:00:00+00', EXTRACT(YEAR FROM '2021-01-20 10:00:00+00'::timestamp), 1, 1),
            (3, 'E3', '2021-02-10 10:00:00+00', EXTRACT(YEAR FROM '2021-02-10 10:00:00+00'::timestamp), 1, 1),
            (4, 'S1', '2021-03-10 10:00:00+00', EXTRACT(YEAR FROM '2021-03-10 10:00:00+00'::timestamp), 2, 1);
            """)
        )
        test_db.commit()
        
        # Refresh materialized view to include new data
        test_db.execute(text("REFRESH MATERIALIZED VIEW mv_dept_mean"))
        test_db.commit()
        
        response = client.get("/api/v1/analytics/departments/above-average?year=2021")
        assert response.status_code == 200
        data = response.json()
        assert data["year"] == 2021
        assert data["mean_hires"] == 2.0  # (3+1)/2
        assert len(data["data"]) == 1
        assert data["data"][0]["department"] == "Engineering"
        assert data["data"][0]["hired"] == 3
    
    def test_departments_above_average_csv_format(self, client, test_db):
        """Test departments above average with CSV format"""
        response = client.get("/api/v1/analytics/departments/above-average?year=2021&format=csv")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]


class TestErrorCases:
    def test_invalid_year_parameter(self, client):
        """Test analytics endpoints with invalid year"""
        response = client.get("/api/v1/analytics/hired/by-quarter?year=1999")
        assert response.status_code == 422  # Validation error
    
    def test_missing_file_upload(self, client):
        """Test CSV upload without file"""
        response = client.post("/api/v1/upload/csv/departments")
        assert response.status_code == 422  # Missing file 