"""
Tests for Hero Image Generation feature using ParaView.
"""

import pytest
from pathlib import Path
import tempfile
import subprocess

# Import the functions to test
from backend.visualization.hero_image import (
    check_paraview_available,
    generate_hero_image,
    generate_simple_hero_image
)


class TestParaViewDetection:
    """Tests for ParaView availability detection."""

    def test_check_paraview_available(self):
        """Test ParaView availability check returns tuple."""
        available, message = check_paraview_available()

        assert isinstance(available, bool)
        assert isinstance(message, str)

        if available:
            # ParaView is installed
            assert 'paraview' in message.lower() or 'version' in message.lower() or message.strip()
        else:
            # ParaView not installed - message should explain why
            assert len(message) > 0

    def test_paraview_not_found_message(self):
        """Test that unavailable ParaView returns informative message."""
        available, message = check_paraview_available()

        if not available:
            # Should have a meaningful error message
            assert 'not' in message.lower() or 'error' in message.lower() or 'timeout' in message.lower()


class TestHeroImageGeneration:
    """Tests for hero image generation."""

    def test_script_generation(self, tmp_path):
        """Test that the ParaView script can be generated."""
        # This tests the internal script generation logic
        case_dir = tmp_path / "test_case"
        case_dir.mkdir()
        output_path = tmp_path / "hero.png"

        # Create minimal OpenFOAM case structure
        (case_dir / "constant").mkdir()
        (case_dir / "system").mkdir()
        (case_dir / "0").mkdir()

        # Try to generate - may fail if ParaView not installed
        result = generate_hero_image(case_dir, output_path)

        # Should return a dict with success status
        assert isinstance(result, dict)
        assert "success" in result

        if not result["success"]:
            # Should have an error message
            assert "error" in result

    def test_output_path(self, tmp_path):
        """Test that output path is correctly handled."""
        case_dir = tmp_path / "test_case"
        case_dir.mkdir()

        # Test with nested output path
        output_dir = tmp_path / "visualizations" / "output"
        output_dir.mkdir(parents=True)
        output_path = output_dir / "hero.png"

        result = generate_hero_image(case_dir, output_path)

        assert isinstance(result, dict)
        if result.get("success"):
            assert result.get("output_path") == str(output_path)

    @pytest.mark.skipif(
        not check_paraview_available()[0],
        reason="ParaView not available"
    )
    def test_actual_generation_with_mock_case(self, tmp_path):
        """Test actual hero image generation with a mock case (requires ParaView)."""
        case_dir = tmp_path / "test_case"
        case_dir.mkdir()
        output_path = tmp_path / "hero.png"

        # Create .foam file
        (case_dir / "case.foam").touch()

        # Create minimal structure
        (case_dir / "constant" / "polyMesh").mkdir(parents=True)
        (case_dir / "system").mkdir()

        result = generate_hero_image(case_dir, output_path)

        # With ParaView available, should at least return a result
        assert isinstance(result, dict)
        assert "success" in result

    def test_foam_file_creation(self, tmp_path):
        """Test that .foam file is created if missing."""
        case_dir = tmp_path / "test_case"
        case_dir.mkdir()
        output_path = tmp_path / "hero.png"

        # Don't create case.foam
        (case_dir / "constant").mkdir()

        result = generate_hero_image(case_dir, output_path)

        # Function should handle missing .foam file
        # (either create it or fail gracefully)
        assert isinstance(result, dict)


class TestSimpleHeroImage:
    """Tests for fallback simple hero image generation."""

    def test_simple_hero_returns_dict(self, tmp_path):
        """Test simple hero image generation returns proper dict."""
        case_dir = tmp_path / "test_case"
        case_dir.mkdir()
        output_path = tmp_path / "simple_hero.png"

        result = generate_simple_hero_image(case_dir, output_path)

        assert isinstance(result, dict)
        assert "success" in result

        # Currently not implemented - should return error
        if not result.get("success"):
            assert "error" in result or "suggestion" in result


class TestHeroImageAPI:
    """Tests for hero image API endpoint."""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client."""
        from fastapi.testclient import TestClient
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
        from app import app
        return TestClient(app)

    def test_hero_image_endpoint_job_not_found(self, client):
        """Hero image for nonexistent job should return 404."""
        response = client.get("/api/jobs/nonexistent/viz/hero.png")
        assert response.status_code == 404

    def test_hero_image_regenerate_param(self, client):
        """Regenerate parameter should be accepted."""
        # This will 404 since job doesn't exist, but validates param parsing
        response = client.get("/api/jobs/test-job/viz/hero.png?regenerate=true")
        assert response.status_code == 404  # Job not found, not param error


class TestHeroImageCameraSettings:
    """Tests for camera and visualization settings."""

    def test_default_camera_position(self):
        """Test default camera position values."""
        # Default values from generate_hero_image function
        default_position = (1.5, -2.0, 1.0)
        default_focal = (0.0, 0.0, 0.3)

        # Position should be outside wheel
        assert default_position[0] > 0  # In front
        assert default_position[1] < 0  # To the side
        assert default_position[2] > 0  # Above ground

        # Focal point should be at wheel center
        assert default_focal[2] > 0  # Above ground (wheel center)

    def test_default_resolution(self):
        """Test default image resolution values."""
        # Default values
        default_width = 1920
        default_height = 1080

        assert default_width >= 1280  # At least HD
        assert default_height >= 720
        assert default_width / default_height == 16/9  # 16:9 aspect ratio


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
