"""
Tests for validation gap improvements (Issues #23, #24, #25).

Issue #23: Wall BC Only rotation method
Issue #24: surfaceFeatureExtract step
Issue #25: Increased pro mesh resolution

Unit tests verify generate_case_files() output.
E2E tests verify the API accepts wall_bc and produces correct configs.
"""

import pytest
import asyncio
import struct
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from fastapi.testclient import TestClient
from app import app, generate_case_files


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_stl(tmp_path):
    """Create a simple valid binary STL file."""
    stl_path = tmp_path / "test_wheel.stl"

    vertices = [
        (0.0, 0.0, 0.0),
        (0.65, 0.0, 0.0),
        (0.325, 0.65, 0.0),
        (0.325, 0.325, 0.65)
    ]
    faces = [(0, 1, 2), (0, 1, 3), (1, 2, 3), (2, 0, 3)]

    with open(stl_path, 'wb') as f:
        f.write(b"binary STL - test wheel".ljust(80, b'\x00'))
        f.write(struct.pack('<I', len(faces)))
        for face in faces:
            f.write(struct.pack('<3f', 0.0, 0.0, 0.0))
            for idx in face:
                f.write(struct.pack('<3f', *vertices[idx]))
            f.write(struct.pack('<H', 0))

    return stl_path


@pytest.fixture
def case_dir(tmp_path):
    """Create a temporary case directory with required structure."""
    case = tmp_path / "test_case"
    case.mkdir()
    return case


@pytest.fixture
def base_config():
    """Minimal config dict for generate_case_files."""
    return {
        "speed": 13.9,
        "yaw_angles": [15],
        "omega": 42.77,
        "air": {"rho": 1.225, "nu": 1.48e-5},
        "wheel_radius": 0.325,
        "aref": 0.0225,
        "rolling_enabled": True,
        "ground_type": "moving",
        "quality": "standard",
        "rotation_method": "wall_bc",
    }


# ============================================================================
# Issue #23: Wall BC Only rotation method
# ============================================================================

class TestWallBCRotationUnit:
    """Unit tests for wall_bc rotation method in generate_case_files."""

    def test_wall_bc_applies_rotating_wall_velocity(self, case_dir, base_config):
        """wall_bc mode should produce rotatingWallVelocity BC on the wheel patch."""
        base_config["rotation_method"] = "wall_bc"
        asyncio.run(generate_case_files(case_dir, base_config))

        u_file = (case_dir / "0" / "U").read_text()
        assert "rotatingWallVelocity" in u_file
        assert "omega" in u_file

    def test_wall_bc_writes_empty_mrf(self, case_dir, base_config):
        """wall_bc mode should produce an empty MRFProperties (no active MRF)."""
        base_config["rotation_method"] = "wall_bc"
        asyncio.run(generate_case_files(case_dir, base_config))

        mrf = (case_dir / "constant" / "MRFProperties").read_text()
        assert "MRFProperties" in mrf
        # Should NOT contain an active MRF zone
        assert "active      true" not in mrf
        assert "cellZone" not in mrf

    def test_wall_bc_no_cellzone_in_snappy(self, case_dir, base_config):
        """wall_bc mode should NOT create cellZone/faceZone in snappyHexMeshDict."""
        base_config["rotation_method"] = "wall_bc"
        asyncio.run(generate_case_files(case_dir, base_config))

        snappy = (case_dir / "system" / "snappyHexMeshDict").read_text()
        # rotatingZone geometry should still exist for refinement
        assert "rotatingZone" in snappy
        # But no cellZone/faceZone directives
        assert "cellZone" not in snappy
        assert "faceZone" not in snappy

    def test_mrf_mode_has_cellzone_in_snappy(self, case_dir, base_config):
        """MRF mode should still create cellZone/faceZone in snappyHexMeshDict."""
        base_config["rotation_method"] = "mrf"
        asyncio.run(generate_case_files(case_dir, base_config))

        snappy = (case_dir / "system" / "snappyHexMeshDict").read_text()
        assert "cellZone rotatingZone" in snappy
        assert "faceZone rotatingZoneFaces" in snappy

    def test_mrf_mode_writes_active_mrf(self, case_dir, base_config):
        """MRF mode should write active MRFProperties with cellZone."""
        base_config["rotation_method"] = "mrf"
        asyncio.run(generate_case_files(case_dir, base_config))

        mrf = (case_dir / "constant" / "MRFProperties").read_text()
        assert "active      true" in mrf
        assert "cellZone    rotatingZone" in mrf
        assert "omega" in mrf

    def test_static_wheel_no_rotation(self, case_dir, base_config):
        """With rolling disabled, wheel should get fixedValue zero velocity."""
        base_config["rolling_enabled"] = False
        base_config["rotation_method"] = "wall_bc"
        asyncio.run(generate_case_files(case_dir, base_config))

        u_file = (case_dir / "0" / "U").read_text()
        assert "fixedValue" in u_file
        assert "rotatingWallVelocity" not in u_file


class TestWallBCRotationE2E:
    """E2E tests for wall_bc rotation method through the API."""

    def test_simulate_accepts_wall_bc(self, client, sample_stl):
        """API should accept wall_bc as a valid rotation_method."""
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
                "name": "Wall BC Test",
                "speed": "13.9",
                "yaw_angles": "0",
                "quality": "basic",
                "rolling_enabled": "true",
                "rotation_method": "wall_bc"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

        # Verify config stored correctly
        job_resp = client.get(f"/api/jobs/{data['job_id']}")
        job = job_resp.json()
        assert job["config"]["rotation_method"] == "wall_bc"

    def test_ui_dropdown_has_wall_bc_option(self, client):
        """The index page should contain the wall_bc option in the dropdown."""
        response = client.get("/")
        assert response.status_code == 200
        assert 'value="wall_bc"' in response.text
        assert "Wall BC Only" in response.text

    def test_wall_bc_is_default_selection(self, client):
        """wall_bc should be the default selected rotation method."""
        response = client.get("/")
        html = response.text
        # Find the wall_bc option and check it has 'selected'
        assert 'value="wall_bc" selected' in html


# ============================================================================
# Issue #24: surfaceFeatureExtract step
# ============================================================================

class TestSurfaceFeatureExtractUnit:
    """Unit tests for surfaceFeaturesDict generation."""

    def test_sfe_dict_generated(self, case_dir, base_config):
        """generate_case_files should create surfaceFeaturesDict."""
        asyncio.run(generate_case_files(case_dir, base_config))

        sfe_path = case_dir / "system" / "surfaceFeaturesDict"
        assert sfe_path.exists()

    def test_sfe_dict_references_wheel_stl(self, case_dir, base_config):
        """surfaceFeaturesDict should reference wheel.stl."""
        asyncio.run(generate_case_files(case_dir, base_config))

        sfe = (case_dir / "system" / "surfaceFeaturesDict").read_text()
        assert "wheel.stl" in sfe

    def test_sfe_dict_has_included_angle(self, case_dir, base_config):
        """surfaceFeaturesDict should use includedAngle 150."""
        asyncio.run(generate_case_files(case_dir, base_config))

        sfe = (case_dir / "system" / "surfaceFeaturesDict").read_text()
        assert "includedAngle" in sfe
        assert "150" in sfe

    def test_sfe_dict_has_surfaces_entry(self, case_dir, base_config):
        """surfaceFeaturesDict should list wheel.stl in surfaces block."""
        asyncio.run(generate_case_files(case_dir, base_config))

        sfe = (case_dir / "system" / "surfaceFeaturesDict").read_text()
        assert "surfaces" in sfe
        assert '"wheel.stl"' in sfe

    def test_snappy_references_emesh(self, case_dir, base_config):
        """snappyHexMeshDict should reference wheel.eMesh in features."""
        asyncio.run(generate_case_files(case_dir, base_config))

        snappy = (case_dir / "system" / "snappyHexMeshDict").read_text()
        assert "wheel.eMesh" in snappy

    def test_emesh_level_matches_max_surface_level(self, case_dir, base_config):
        """The .eMesh refinement level should match the max surface level of the preset."""
        # Standard preset has surfaceLevel (3, 4) -> max level 4
        base_config["quality"] = "standard"
        asyncio.run(generate_case_files(case_dir, base_config))

        snappy = (case_dir / "system" / "snappyHexMeshDict").read_text()
        assert "wheel.eMesh" in snappy
        # Standard preset surfaceLevel[1] = 4
        assert "level 4" in snappy

    def test_emesh_level_pro_quality(self, case_dir, base_config):
        """Pro preset eMesh level should be 6 (updated surfaceLevel max)."""
        base_config["quality"] = "pro"
        asyncio.run(generate_case_files(case_dir, base_config))

        snappy = (case_dir / "system" / "snappyHexMeshDict").read_text()
        assert "wheel.eMesh" in snappy
        assert "level 6" in snappy


# ============================================================================
# Issue #25: Increased pro mesh resolution
# ============================================================================

class TestProMeshResolutionUnit:
    """Unit tests for updated pro mesh preset values."""

    def test_pro_max_global_cells_increased(self, case_dir, base_config):
        """Pro preset should have maxGlobalCells = 15000000."""
        base_config["quality"] = "pro"
        asyncio.run(generate_case_files(case_dir, base_config))

        snappy = (case_dir / "system" / "snappyHexMeshDict").read_text()
        assert "15000000" in snappy

    def test_pro_surface_level_max_six(self, case_dir, base_config):
        """Pro preset should have max surface level 6."""
        base_config["quality"] = "pro"
        asyncio.run(generate_case_files(case_dir, base_config))

        snappy = (case_dir / "system" / "snappyHexMeshDict").read_text()
        # refinementSurfaces should have level (4 6)
        assert "level (4 6)" in snappy

    def test_pro_background_mesh_increased(self, case_dir, base_config):
        """Pro preset should have increased background mesh (120, 60, 42)."""
        base_config["quality"] = "pro"
        asyncio.run(generate_case_files(case_dir, base_config))

        block_mesh = (case_dir / "system" / "blockMeshDict").read_text()
        assert "(120 60 42)" in block_mesh

    def test_standard_preset_unchanged(self, case_dir, base_config):
        """Standard preset should remain at 2M cells."""
        base_config["quality"] = "standard"
        asyncio.run(generate_case_files(case_dir, base_config))

        snappy = (case_dir / "system" / "snappyHexMeshDict").read_text()
        assert "2000000" in snappy
        assert "level (3 4)" in snappy

    def test_basic_preset_unchanged(self, case_dir, base_config):
        """Basic preset should remain at 500k cells."""
        base_config["quality"] = "basic"
        asyncio.run(generate_case_files(case_dir, base_config))

        snappy = (case_dir / "system" / "snappyHexMeshDict").read_text()
        assert "500000" in snappy
        assert "level (2 3)" in snappy

    def test_ui_shows_12m_for_pro(self, client):
        """The UI should show ~12M cells for pro quality."""
        response = client.get("/")
        assert "~12M cells" in response.text


class TestProMeshResolutionE2E:
    """E2E tests for pro mesh resolution through the API."""

    def test_simulate_with_pro_quality(self, client, sample_stl):
        """API should accept pro quality and store it in job config."""
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
                "name": "Pro Quality Test",
                "speed": "13.9",
                "yaw_angles": "0",
                "quality": "pro",
                "rolling_enabled": "true",
                "rotation_method": "wall_bc"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

        job_resp = client.get(f"/api/jobs/{data['job_id']}")
        job = job_resp.json()
        assert job["config"]["quality"] == "pro"


# ============================================================================
# Combined integration: all three features together
# ============================================================================

class TestCombinedFeatures:
    """Test all three features working together."""

    def test_wall_bc_pro_with_feature_extract(self, case_dir, base_config):
        """wall_bc + pro quality should produce correct case files with feature extraction."""
        base_config["rotation_method"] = "wall_bc"
        base_config["quality"] = "pro"
        asyncio.run(generate_case_files(case_dir, base_config))

        # Check all expected files exist
        assert (case_dir / "0" / "U").exists()
        assert (case_dir / "constant" / "MRFProperties").exists()
        assert (case_dir / "system" / "snappyHexMeshDict").exists()
        assert (case_dir / "system" / "surfaceFeaturesDict").exists()
        assert (case_dir / "system" / "blockMeshDict").exists()

        # Verify wall_bc specifics
        u_file = (case_dir / "0" / "U").read_text()
        assert "rotatingWallVelocity" in u_file

        mrf = (case_dir / "constant" / "MRFProperties").read_text()
        assert "active      true" not in mrf

        # Verify feature extract
        sfe = (case_dir / "system" / "surfaceFeaturesDict").read_text()
        assert "wheel.stl" in sfe

        # Verify pro mesh settings
        snappy = (case_dir / "system" / "snappyHexMeshDict").read_text()
        assert "15000000" in snappy
        assert "level (4 6)" in snappy
        assert "wheel.eMesh" in snappy
        # No cellZone for wall_bc
        assert "cellZone" not in snappy

        block_mesh = (case_dir / "system" / "blockMeshDict").read_text()
        assert "(120 60 42)" in block_mesh

    def test_mrf_pro_with_feature_extract(self, case_dir, base_config):
        """MRF + pro quality should still produce cellZone and active MRF."""
        base_config["rotation_method"] = "mrf"
        base_config["quality"] = "pro"
        asyncio.run(generate_case_files(case_dir, base_config))

        snappy = (case_dir / "system" / "snappyHexMeshDict").read_text()
        assert "cellZone rotatingZone" in snappy
        assert "faceZone rotatingZoneFaces" in snappy

        mrf = (case_dir / "constant" / "MRFProperties").read_text()
        assert "active      true" in mrf


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
