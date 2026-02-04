"""
Tests for database persistence module.

Tests issue #18: Persist Jobs to Database
"""

import pytest
import tempfile
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def setup_test_db(tmp_path):
    """Use a temporary database for each test."""
    test_db_path = tmp_path / "test_wheelflow.db"

    # Import and patch the database module
    from backend import database as db

    # Save original path and set test path
    original_path = db.DB_PATH
    db.DB_PATH = test_db_path
    db.init_db()

    yield db

    # Restore original path
    db.DB_PATH = original_path


class TestDatabaseModule:
    """Tests for the database module."""

    def test_create_job(self, setup_test_db):
        """Test creating a new job."""
        db = setup_test_db
        config = {"speed": 13.9, "yaw_angles": [0, 5, 10]}

        job = db.create_job("test-job-001", config)

        assert job is not None
        assert job["id"] == "test-job-001"
        assert job["status"] == "pending"
        assert job["config"]["speed"] == 13.9
        assert job["config"]["yaw_angles"] == [0, 5, 10]

    def test_get_job(self, setup_test_db):
        """Test retrieving a job by ID."""
        db = setup_test_db
        db.create_job("test-job-002", {"speed": 15.0})

        job = db.get_job("test-job-002")

        assert job is not None
        assert job["id"] == "test-job-002"
        assert job["config"]["speed"] == 15.0

    def test_get_job_not_found(self, setup_test_db):
        """Test retrieving a non-existent job returns None."""
        db = setup_test_db

        job = db.get_job("nonexistent-job")

        assert job is None

    def test_get_all_jobs(self, setup_test_db):
        """Test retrieving all jobs."""
        db = setup_test_db
        db.create_job("job-a", {"name": "Job A"})
        db.create_job("job-b", {"name": "Job B"})
        db.create_job("job-c", {"name": "Job C"})

        all_jobs = db.get_all_jobs()

        assert len(all_jobs) == 3
        job_ids = [j["id"] for j in all_jobs]
        assert "job-a" in job_ids
        assert "job-b" in job_ids
        assert "job-c" in job_ids

    def test_update_job_status(self, setup_test_db):
        """Test updating job status."""
        db = setup_test_db
        db.create_job("test-job-003", {})

        updated = db.update_job_status("test-job-003", "running")

        assert updated["status"] == "running"
        assert updated["started_at"] is not None

    def test_update_job_status_complete(self, setup_test_db):
        """Test updating job status to complete sets completed_at."""
        db = setup_test_db
        db.create_job("test-job-004", {})

        updated = db.update_job_status("test-job-004", "complete")

        assert updated["status"] == "complete"
        assert updated["completed_at"] is not None

    def test_set_job_results(self, setup_test_db):
        """Test setting job results."""
        db = setup_test_db
        db.create_job("test-job-005", {})
        results = {"drag": 1.31, "lift": 0.5, "Cd": 0.49}

        updated = db.set_job_results("test-job-005", results)

        assert updated["status"] == "complete"
        assert updated["results"]["drag"] == 1.31
        assert updated["results"]["Cd"] == 0.49

    def test_set_job_error(self, setup_test_db):
        """Test setting job error."""
        db = setup_test_db
        db.create_job("test-job-006", {})

        updated = db.set_job_error("test-job-006", "Mesh generation failed")

        assert updated["status"] == "failed"
        assert updated["error"] == "Mesh generation failed"

    def test_delete_job(self, setup_test_db):
        """Test deleting a job."""
        db = setup_test_db
        db.create_job("test-job-007", {})

        result = db.delete_job("test-job-007")

        assert result is True
        assert db.get_job("test-job-007") is None

    def test_delete_job_not_found(self, setup_test_db):
        """Test deleting a non-existent job returns False."""
        db = setup_test_db

        result = db.delete_job("nonexistent")

        assert result is False

    def test_job_exists(self, setup_test_db):
        """Test checking if job exists."""
        db = setup_test_db
        db.create_job("test-job-008", {})

        assert db.job_exists("test-job-008") is True
        assert db.job_exists("nonexistent") is False

    def test_create_job_with_batch_info(self, setup_test_db):
        """Test creating a job with batch information."""
        db = setup_test_db

        job = db.create_job(
            "batch-job-001",
            {"speed": 13.9},
            batch_id="batch-123",
            batch_yaw_angles=[0, 5, 10, 15],
            yaw_angle=5.0
        )

        assert job["batch_id"] == "batch-123"
        assert job["batch_yaw_angles"] == [0, 5, 10, 15]
        assert job["yaw_angle"] == 5.0

    def test_job_persistence_across_connections(self, setup_test_db):
        """Test that jobs persist across database connections."""
        db = setup_test_db

        # Create job
        db.create_job("persist-test", {"data": "test"})

        # Close and reopen connection (simulated by getting job again)
        job = db.get_job("persist-test")

        assert job is not None
        assert job["config"]["data"] == "test"


class TestDatabaseIntegration:
    """Integration tests for database with app."""

    def test_jobs_loaded_on_startup(self, setup_test_db):
        """Test that jobs are loaded from database on app startup."""
        db = setup_test_db

        # Create some jobs directly in database
        db.create_job("startup-job-1", {"name": "Job 1"})
        db.create_job("startup-job-2", {"name": "Job 2"})

        # Simulate loading jobs like app does on startup
        jobs = {job['id']: job for job in db.get_all_jobs()}

        assert len(jobs) == 2
        assert "startup-job-1" in jobs
        assert "startup-job-2" in jobs
