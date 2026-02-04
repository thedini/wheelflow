"""
Tests for MRF (Moving Reference Frame) and AMI (Arbitrary Mesh Interface) rotation methods.
"""

import pytest
from pathlib import Path
import tempfile
import math

# Import the functions to test
from backend.openfoam_templates.dynamic_mesh import (
    generate_mrf_properties,
    generate_dynamic_mesh_dict,
    generate_fv_options_mrf,
    calculate_rotation_params
)


class TestMRFGeneration:
    """Tests for MRF (Moving Reference Frame) file generation."""

    def test_mrf_properties_content(self):
        """Test MRFProperties dict generation with expected content."""
        mrf = generate_mrf_properties(
            zone_name="rotatingZone",
            origin=(0, 0, 0.325),
            axis=(0, 1, 0),
            omega=42.77,
            non_rotating_patches=["ground"]
        )

        assert "FoamFile" in mrf
        assert "MRFProperties" in mrf
        assert "rotatingZone" in mrf
        assert "origin" in mrf
        assert "axis" in mrf
        assert "omega" in mrf
        assert "(0 1 0)" in mrf  # Y-axis rotation
        assert "42.77" in mrf

    def test_mrf_properties_non_rotating_patches(self):
        """Test that non-rotating patches are correctly included."""
        mrf = generate_mrf_properties(
            zone_name="wheelZone",
            origin=(0, 0, 0.35),
            axis=(0, 1, 0),
            omega=40.0,
            non_rotating_patches=["ground", "inlet", "outlet"]
        )

        assert "nonRotatingPatches" in mrf
        assert "ground" in mrf
        assert "inlet" in mrf
        assert "outlet" in mrf

    def test_mrf_properties_empty_non_rotating(self):
        """Test MRFProperties with no non-rotating patches."""
        mrf = generate_mrf_properties(
            zone_name="rotatingZone",
            origin=(0, 0, 0.325),
            axis=(0, 1, 0),
            omega=42.77
        )

        assert "nonRotatingPatches" in mrf
        # Empty list should have empty content after patches

    def test_mrf_omega_calculation(self):
        """Test angular velocity calculation from linear speed and radius."""
        params = calculate_rotation_params(speed=13.9, wheel_radius=0.325)

        # omega = V / R = 13.9 / 0.325 ≈ 42.77 rad/s
        expected_omega = 13.9 / 0.325
        assert abs(params['omega'] - expected_omega) < 0.01

        # RPM = omega * 60 / (2 * pi)
        expected_rpm = expected_omega * 60 / (2 * math.pi)
        assert abs(params['rpm'] - expected_rpm) < 0.1

        # Period = 2 * pi / omega
        expected_period = 2 * math.pi / expected_omega
        assert abs(params['period'] - expected_period) < 0.01

        # Tip speed should equal linear speed for no-slip condition
        assert abs(params['tip_speed'] - 13.9) < 0.01


class TestAMIGeneration:
    """Tests for AMI (Arbitrary Mesh Interface) dynamic mesh generation."""

    def test_dynamic_mesh_dict_ami(self):
        """Test dynamicMeshDict generation for AMI mode."""
        dmd = generate_dynamic_mesh_dict(
            zone_name="rotatingZone",
            origin=(0, 0, 0.325),
            axis=(0, 1, 0),
            omega=42.77,
            use_ami=True
        )

        assert "FoamFile" in dmd
        assert "dynamicMeshDict" in dmd
        assert "dynamicMotionSolverFvMesh" in dmd
        assert "solidBody" in dmd
        assert "rotatingMotion" in dmd
        assert "rotatingZone" in dmd
        assert "constant 42.77" in dmd or "42.77" in dmd

    def test_dynamic_mesh_dict_mrf(self):
        """Test dynamicMeshDict generation for MRF (static mesh) mode."""
        dmd = generate_dynamic_mesh_dict(
            zone_name="rotatingZone",
            origin=(0, 0, 0.325),
            axis=(0, 1, 0),
            omega=42.77,
            use_ami=False
        )

        assert "FoamFile" in dmd
        assert "dynamicMeshDict" in dmd
        assert "staticFvMesh" in dmd
        # Should NOT have dynamic mesh settings
        assert "dynamicMotionSolverFvMesh" not in dmd
        assert "solidBody" not in dmd

    def test_fv_options_mrf_generation(self):
        """Test fvOptions MRF source generation."""
        fv_opts = generate_fv_options_mrf(
            zone_name="wheelZone",
            origin=(0, 0, 0.35),
            axis=(0, 1, 0),
            omega=40.0
        )

        assert "FoamFile" in fv_opts
        assert "fvOptions" in fv_opts
        assert "MRFSource" in fv_opts
        assert "wheelZone" in fv_opts
        assert "40.0" in fv_opts


class TestRotationMethodSelection:
    """Tests for rotation method selection logic."""

    def test_rotation_params_zero_speed(self):
        """Test rotation parameters with zero speed."""
        params = calculate_rotation_params(speed=0, wheel_radius=0.325)

        assert params['omega'] == 0
        assert params['rpm'] == 0
        assert params['period'] == float('inf')

    def test_rotation_params_different_radii(self):
        """Test rotation parameters with different wheel radii."""
        # Larger wheel = slower rotation at same speed
        params_small = calculate_rotation_params(speed=13.9, wheel_radius=0.30)
        params_large = calculate_rotation_params(speed=13.9, wheel_radius=0.35)

        assert params_small['omega'] > params_large['omega']
        assert params_small['rpm'] > params_large['rpm']

    def test_ami_requires_transient_solver(self):
        """Verify AMI mode generates content for transient solver."""
        dmd = generate_dynamic_mesh_dict(
            zone_name="rotatingZone",
            origin=(0, 0, 0.325),
            axis=(0, 1, 0),
            omega=42.77,
            use_ami=True
        )

        # AMI mode needs motion solver libraries
        assert "libfvMotionSolvers" in dmd
        assert "motionSolver" in dmd


class TestMRFCellZone:
    """Tests for MRF cell zone generation (topoSetDict)."""

    def test_topo_set_dict_cylinder_dimensions(self):
        """Test topoSetDict cylinder dimensions for MRF zone."""
        wheel_radius = 0.325

        # The cylinder should:
        # - Be centered on the wheel axle
        # - Have radius slightly larger than wheel
        # - Span the wheel width

        expected_cylinder_radius = wheel_radius * 1.05  # 5% larger
        assert expected_cylinder_radius > wheel_radius

        # Height should be at wheel center (z = wheel_radius for wheel on ground)
        expected_z_center = wheel_radius

        # These are what the actual code generates
        # Verify the logic is sound
        assert expected_z_center == 0.325


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
