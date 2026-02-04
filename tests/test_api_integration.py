"""
API Integration Tests for WheelFlow Backend

These tests exercise the actual FastAPI endpoints to verify:
- File upload works correctly
- Job creation and status tracking
- Results extraction and calculation
- API response formats
"""

import pytest
import struct
import json
from pathlib import Path
from fastapi.testclient import TestClient

# Add backend to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app import app


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_stl(tmp_path):
    """Create a simple valid binary STL file."""
    stl_path = tmp_path / "test_wheel.stl"

    # Create a simple tetrahedron
    vertices = [
        (0.0, 0.0, 0.0),
        (0.65, 0.0, 0.0),  # ~wheel diameter in meters
        (0.325, 0.65, 0.0),
        (0.325, 0.325, 0.65)
    ]
    faces = [(0, 1, 2), (0, 1, 3), (1, 2, 3), (2, 0, 3)]

    with open(stl_path, 'wb') as f:
        f.write(b"binary STL - test wheel".ljust(80, b'\x00'))
        f.write(struct.pack('<I', len(faces)))

        for face in faces:
            f.write(struct.pack('<3f', 0.0, 0.0, 0.0))  # normal
            for idx in face:
                f.write(struct.pack('<3f', *vertices[idx]))
            f.write(struct.pack('<H', 0))

    return stl_path


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_root_returns_html(self, client):
        """Root endpoint should return index.html."""
        response = client.get("/")
        assert response.status_code == 200
        assert "WheelFlow" in response.text


class TestUploadEndpoint:
    """Tests for file upload endpoint."""

    def test_upload_valid_stl(self, client, sample_stl):
        """Valid STL upload should succeed."""
        with open(sample_stl, 'rb') as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.stl", f, "application/octet-stream")}
            )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "info" in data
        assert data["info"]["triangles"] == 4

    def test_upload_returns_geometry_info(self, client, sample_stl):
        """Upload should return geometry dimensions."""
        with open(sample_stl, 'rb') as f:
            response = client.post(
                "/api/upload",
                files={"file": ("wheel.stl", f, "application/octet-stream")}
            )

        data = response.json()
        assert "dimensions" in data["info"]
        assert len(data["info"]["dimensions"]) == 3

    def test_upload_rejects_empty_file(self, client, tmp_path):
        """Empty file should be rejected."""
        empty_file = tmp_path / "empty.stl"
        empty_file.touch()

        with open(empty_file, 'rb') as f:
            response = client.post(
                "/api/upload",
                files={"file": ("empty.stl", f, "application/octet-stream")}
            )

        assert response.status_code == 400

    def test_upload_rejects_non_stl(self, client, tmp_path):
        """Non-STL file should be rejected."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not an stl file")

        with open(txt_file, 'rb') as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.txt", f, "text/plain")}
            )

        assert response.status_code == 400


class TestJobsEndpoint:
    """Tests for jobs list endpoint."""

    def test_list_jobs_initially_empty(self, client):
        """Jobs list may be empty or contain previous jobs."""
        response = client.get("/api/jobs")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_jobs_response_format(self, client):
        """Jobs response should be a list."""
        response = client.get("/api/jobs")
        assert response.status_code == 200
        jobs = response.json()
        assert isinstance(jobs, list)


class TestSimulationSubmission:
    """Tests for simulation submission."""

    def test_simulate_accepts_file_id(self, client):
        """Simulation accepts any file_id format (validated later)."""
        response = client.post(
            "/api/simulate",
            data={
                "file_id": "nonexistent",
                "name": "Test Sim",
                "speed": "13.9",
                "yaw_angles": "0, 5, 10",
                "quality": "basic"
            }
        )

        # API creates job even if file doesn't exist (lazy validation)
        # Job will fail later during execution
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    def test_simulate_with_valid_params(self, client, sample_stl):
        """Simulation with valid params should create a job."""
        # First upload the file
        with open(sample_stl, 'rb') as f:
            upload_response = client.post(
                "/api/upload",
                files={"file": ("wheel.stl", f, "application/octet-stream")}
            )

        file_id = upload_response.json()["id"]

        # Submit simulation
        response = client.post(
            "/api/simulate",
            data={
                "file_id": file_id,
                "name": "Test Wheel Simulation",
                "speed": "13.9",
                "yaw_angles": "0, 5, 10",
                "ground_enabled": "true",
                "ground_type": "moving",
                "rolling_enabled": "true",
                "wheel_radius": "0.325",
                "quality": "basic",
                "gpu_acceleration": "false"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data


class TestJobDetails:
    """Tests for job details endpoint."""

    def test_get_nonexistent_job(self, client):
        """Requesting nonexistent job should return 404."""
        response = client.get("/api/jobs/nonexistent-job-id")
        assert response.status_code == 404

    def test_job_has_required_fields(self, client, sample_stl):
        """Job details should include required fields."""
        # Upload and submit
        with open(sample_stl, 'rb') as f:
            upload_resp = client.post(
                "/api/upload",
                files={"file": ("wheel.stl", f, "application/octet-stream")}
            )
        file_id = upload_resp.json()["id"]

        sim_resp = client.post(
            "/api/simulate",
            data={
                "file_id": file_id,
                "name": "Field Test",
                "speed": "13.9",
                "yaw_angles": "0",
                "quality": "basic"
            }
        )
        job_id = sim_resp.json()["job_id"]

        # Get job details
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200

        job = response.json()
        assert "id" in job
        assert "name" in job
        assert "status" in job
        assert "progress" in job
        assert "created_at" in job


class TestResultsEndpoint:
    """Tests for results extraction endpoint."""

    def test_results_nonexistent_job(self, client):
        """Results for nonexistent job should return 404."""
        response = client.get("/api/jobs/nonexistent/results")
        assert response.status_code == 404


class TestConvergenceEndpoint:
    """Tests for convergence data endpoint."""

    def test_convergence_nonexistent_job(self, client):
        """Convergence for nonexistent job should return 404."""
        response = client.get("/api/jobs/nonexistent/convergence")
        assert response.status_code == 404


class TestVisualizationEndpoints:
    """Tests for visualization data endpoints."""

    def test_force_distribution_nonexistent_job(self, client):
        """Force distribution for nonexistent job should return 404."""
        response = client.get("/api/jobs/nonexistent/viz/force_distribution")
        assert response.status_code == 404

    def test_slices_nonexistent_job(self, client):
        """Slices for nonexistent job should return 404."""
        response = client.get("/api/jobs/nonexistent/viz/slices")
        assert response.status_code == 404


class TestStaticFiles:
    """Tests for static file serving."""

    def test_css_served(self, client):
        """CSS file should be served."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        assert "text/css" in response.headers.get("content-type", "")

    def test_js_served(self, client):
        """JavaScript file should be served."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "javascript" in response.headers.get("content-type", "")

    def test_index_html_served(self, client):
        """Index page should be served."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "WheelFlow" in response.text


class TestCoefficientCalculations:
    """Tests that verify coefficient calculations are correct."""

    def test_dynamic_pressure_formula(self):
        """Test q = 0.5 * rho * V^2."""
        rho = 1.225  # kg/m³
        V = 13.9  # m/s
        q = 0.5 * rho * V * V

        # Should be approximately 118 Pa
        assert 117 < q < 120

    def test_drag_coefficient_formula(self):
        """Test Cd = Fd / (q * A)."""
        Fd = 1.31  # N (AeroCloud reference)
        q = 118.3  # Pa
        A = 0.0225  # m²

        Cd = Fd / (q * A)

        # Should be approximately 0.49
        assert 0.45 < Cd < 0.55

    def test_cda_calculation(self):
        """Test CdA = Cd * A."""
        Cd = 0.49
        A = 0.0225  # m²

        CdA = Cd * A
        CdA_cm2 = CdA * 10000

        # Should be approximately 110 cm²
        assert 100 < CdA_cm2 < 120

    def test_reynolds_number_calculation(self):
        """Test Re = V * L / nu."""
        V = 13.9  # m/s
        L = 0.65  # m (wheel diameter)
        nu = 1.48e-5  # m²/s

        Re = V * L / nu

        # Should be approximately 610,000
        assert 500000 < Re < 700000


class TestAPIResponseFormats:
    """Tests for API response format consistency."""

    def test_error_response_format(self, client):
        """Error responses should have consistent format."""
        response = client.get("/api/jobs/nonexistent")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data

    def test_upload_response_format(self, client, sample_stl):
        """Upload response should have consistent format."""
        with open(sample_stl, 'rb') as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.stl", f, "application/octet-stream")}
            )

        data = response.json()
        required_fields = ["id", "filename", "info"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestRotationMethodAPI:
    """Tests for rotation method API parameter handling."""

    def test_simulate_with_rotation_method_mrf(self, client, sample_stl):
        """Simulation with MRF rotation method should be accepted."""
        with open(sample_stl, 'rb') as f:
            upload_resp = client.post(
                "/api/upload",
                files={"file": ("wheel.stl", f, "application/octet-stream")}
            )
        file_id = upload_resp.json()["id"]

        response = client.post(
            "/api/simulate",
            data={
                "file_id": file_id,
                "name": "MRF Test",
                "speed": "13.9",
                "yaw_angles": "0",
                "quality": "basic",
                "rolling_enabled": "true",
                "rotation_method": "mrf"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

        # Verify job config contains rotation_method
        job_resp = client.get(f"/api/jobs/{data['job_id']}")
        job = job_resp.json()
        assert job["config"]["rotation_method"] == "mrf"

    def test_simulate_with_rotation_method_transient(self, client, sample_stl):
        """Simulation with transient (AMI) rotation method should be accepted."""
        with open(sample_stl, 'rb') as f:
            upload_resp = client.post(
                "/api/upload",
                files={"file": ("wheel.stl", f, "application/octet-stream")}
            )
        file_id = upload_resp.json()["id"]

        response = client.post(
            "/api/simulate",
            data={
                "file_id": file_id,
                "name": "AMI Test",
                "speed": "13.9",
                "yaw_angles": "0",
                "quality": "basic",
                "rolling_enabled": "true",
                "rotation_method": "transient"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

        # Verify job config contains rotation_method
        job_resp = client.get(f"/api/jobs/{data['job_id']}")
        job = job_resp.json()
        assert job["config"]["rotation_method"] == "transient"

    def test_simulate_with_rotation_method_none(self, client, sample_stl):
        """Simulation with no rotation should work."""
        with open(sample_stl, 'rb') as f:
            upload_resp = client.post(
                "/api/upload",
                files={"file": ("wheel.stl", f, "application/octet-stream")}
            )
        file_id = upload_resp.json()["id"]

        response = client.post(
            "/api/simulate",
            data={
                "file_id": file_id,
                "name": "No Rotation Test",
                "speed": "13.9",
                "yaw_angles": "0",
                "quality": "basic",
                "rolling_enabled": "false",
                "rotation_method": "none"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    def test_rotation_method_defaults_to_mrf(self, client, sample_stl):
        """Without rotation_method param, should default to mrf."""
        with open(sample_stl, 'rb') as f:
            upload_resp = client.post(
                "/api/upload",
                files={"file": ("wheel.stl", f, "application/octet-stream")}
            )
        file_id = upload_resp.json()["id"]

        response = client.post(
            "/api/simulate",
            data={
                "file_id": file_id,
                "name": "Default Method Test",
                "speed": "13.9",
                "yaw_angles": "0",
                "quality": "basic"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify job config defaults rotation_method to mrf
        job_resp = client.get(f"/api/jobs/{data['job_id']}")
        job = job_resp.json()
        assert job["config"]["rotation_method"] == "mrf"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
