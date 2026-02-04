"""
Tests for job delete endpoint.

Tests issue #1: Delete button for simulations does not work
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def test_cases_dir(tmp_path):
    """Create a temporary cases directory."""
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    return cases_dir


@pytest.fixture
def mock_db():
    """Mock the database module."""
    mock = MagicMock()
    mock.get_all_jobs.return_value = []
    mock.delete_job.return_value = True
    mock.job_exists.return_value = True
    return mock


@pytest.fixture
def client(mock_db, test_cases_dir):
    """Create a test client with mocked dependencies."""
    with patch('backend.app.db', mock_db):
        with patch('backend.app.CASES_DIR', test_cases_dir):
            with patch('backend.app._load_jobs_from_db', return_value={}):
                # Need to reload app module to pick up mocks
                import importlib
                from backend import app as app_module
                importlib.reload(app_module)
                app_module.jobs.clear()
                yield TestClient(app_module.app), app_module.jobs, test_cases_dir, mock_db


class TestDeleteEndpoint:
    """Tests for DELETE /api/jobs/{job_id} endpoint."""

    def test_delete_job_success(self, client):
        """Test successful job deletion."""
        test_client, jobs, cases_dir, mock_db = client

        # Setup: Add a job to the in-memory store
        job_id = "test-delete-001"
        jobs[job_id] = {
            "id": job_id,
            "status": "complete",
            "config": {},
            "results": {}
        }

        # Execute
        response = test_client.delete(f"/api/jobs/{job_id}")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Job deleted successfully"
        assert data["job_id"] == job_id
        assert job_id not in jobs

    def test_delete_job_not_found(self, client):
        """Test deleting a non-existent job returns 404."""
        test_client, jobs, _, _ = client

        response = test_client.delete("/api/jobs/nonexistent-job")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_job_removes_case_directory(self, tmp_path):
        """Test that deleting a job also removes the case directory."""
        # This test needs direct access to verify directory deletion
        # Uses the integration test approach for accurate CASES_DIR patching
        from backend import database as db
        from backend.app import app, jobs, CASES_DIR
        import shutil

        job_id = "test-delete-002"

        # Create the case directory in the actual CASES_DIR
        case_dir = CASES_DIR / job_id
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "test_file.txt").write_text("test content")

        # Add job to memory
        jobs[job_id] = {"id": job_id, "status": "complete"}

        assert case_dir.exists()

        # Execute
        test_client = TestClient(app)
        response = test_client.delete(f"/api/jobs/{job_id}")

        # Verify
        assert response.status_code == 200
        assert not case_dir.exists()

    def test_delete_job_handles_missing_case_directory(self, client):
        """Test deletion works even if case directory doesn't exist."""
        test_client, jobs, cases_dir, _ = client

        # Setup: Add job but don't create case directory
        job_id = "test-delete-003"
        jobs[job_id] = {"id": job_id, "status": "failed"}

        case_dir = cases_dir / job_id
        assert not case_dir.exists()

        # Execute
        response = test_client.delete(f"/api/jobs/{job_id}")

        # Verify - should succeed without error
        assert response.status_code == 200

    def test_delete_running_job(self, client):
        """Test that running jobs can be deleted."""
        test_client, jobs, _, _ = client

        # Setup: Add a running job
        job_id = "test-delete-004"
        jobs[job_id] = {"id": job_id, "status": "running", "progress": 50}

        # Execute
        response = test_client.delete(f"/api/jobs/{job_id}")

        # Verify - deletion should succeed
        assert response.status_code == 200
        assert job_id not in jobs

    def test_delete_queued_job(self, client):
        """Test that queued jobs can be deleted."""
        test_client, jobs, _, _ = client

        # Setup: Add a queued job
        job_id = "test-delete-005"
        jobs[job_id] = {"id": job_id, "status": "queued", "progress": 0}

        # Execute
        response = test_client.delete(f"/api/jobs/{job_id}")

        # Verify
        assert response.status_code == 200
        assert job_id not in jobs


class TestDeleteEndpointIntegration:
    """Integration tests for delete endpoint with real database."""

    def test_delete_persists_to_database(self, tmp_path):
        """Test that deletion removes job from database."""
        test_db_path = tmp_path / "test.db"
        test_cases_dir = tmp_path / "cases"
        test_cases_dir.mkdir()

        # Import and setup database with test path
        from backend import database as db
        original_db_path = db.DB_PATH
        db.DB_PATH = test_db_path
        db.init_db()

        try:
            # Create job in database
            job_id = "persist-delete-001"
            db.create_job(job_id, {"speed": 13.9})
            assert db.job_exists(job_id)

            # Use TestClient with patched paths
            with patch('backend.app.CASES_DIR', test_cases_dir):
                with patch('backend.app.db', db):
                    from backend.app import app, jobs
                    jobs[job_id] = db.get_job(job_id)

                    test_client = TestClient(app)
                    response = test_client.delete(f"/api/jobs/{job_id}")

                    # Verify
                    assert response.status_code == 200
                    assert not db.job_exists(job_id)
        finally:
            db.DB_PATH = original_db_path
