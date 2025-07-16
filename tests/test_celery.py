"""Celery task tests for CSV processing logic.

These tests execute `process_csv_upload` in **eager** mode (configured in
`conftest.py`). They verify that the task:
1. Returns the expected success metadata.
2. Loads the correct number of rows into the database.
"""
from pathlib import Path
import io
import csv as pycsv

import pytest
from sqlalchemy import text

from app.workers.tasks import process_csv_upload


@pytest.fixture
def departments_csv(tmp_path: Path):
    """Create a small departments CSV file and return its path."""
    csv_path = tmp_path / "departments.csv"
    with csv_path.open("w", newline="") as fh:
        writer = pycsv.writer(fh)
        writer.writerow(["id", "department"])
        writer.writerow([101, "QA"])
        writer.writerow([102, "Support"])
        writer.writerow([103, "Operations"])
    return csv_path


@pytest.fixture
def hired_csv(tmp_path: Path, test_db):
    """Create a small hired_employees CSV referencing existing FK rows."""
    # Ensure FK rows exist (department 101, job 201)
    test_db.execute(text("INSERT INTO departments (id, department) VALUES (101, 'QA') ON CONFLICT DO NOTHING"))
    test_db.execute(text("INSERT INTO jobs (id, job) VALUES (201, 'Tester') ON CONFLICT DO NOTHING"))
    test_db.commit()

    csv_path = tmp_path / "hired.csv"
    with csv_path.open("w", newline="") as fh:
        writer = pycsv.writer(fh)
        writer.writerow(["id", "name", "datetime", "department_id", "job_id"])
        writer.writerow([501, "Alice QA", "2021-01-15T10:00:00Z", 101, 201])
        writer.writerow([502, "Bob QA", "2021-02-20T12:00:00Z", 101, 201])
    return csv_path


class TestCeleryCSVProcessing:
    def test_process_departments_csv(self, test_db, departments_csv):
        """Task loads CSV into departments table and reports correct metadata."""
        result = process_csv_upload.delay(str(departments_csv), "departments").get()

        assert result["status"] == "completed"
        assert result["table"] == "departments"
        assert result["rows_processed"] == 3
        assert result["duration_seconds"] >= 0

        count = test_db.execute(text("SELECT COUNT(*) FROM departments WHERE id >= 101"))
        assert count.scalar_one() == 3

    def test_process_hired_employees_csv(self, test_db, hired_csv):
        """Task loads CSV into hired_employees table (with date parsing)."""
        result = process_csv_upload.delay(str(hired_csv), "hired_employees").get()

        assert result["status"] == "completed"
        assert result["table"] == "hired_employees"
        assert result["rows_processed"] == 2

        count = test_db.execute(text("SELECT COUNT(*) FROM hired_employees WHERE id IN (501,502)"))
        assert count.scalar_one() == 2

    def test_invalid_table_raises_retry(self, tmp_path):
        """Supplying an unknown table name causes the task to retry (raises)."""
        dummy_csv = tmp_path / "dummy.csv"
        dummy_csv.write_text("id,name\n1,Test")

        with pytest.raises(Exception):
            # Using apply to surface exception instead of .delay/.get
            process_csv_upload.apply(args=[str(dummy_csv), "unknown_table"]).get()
