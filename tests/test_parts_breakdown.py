"""
Tests for Parts Breakdown feature - drag contribution by wheel component.
"""

import pytest
from pathlib import Path
import tempfile

# Import the functions to test
from backend.visualization.force_distribution import (
    detect_wheel_parts,
    extract_per_part_forces,
    generate_per_part_force_coeffs,
    KNOWN_WHEEL_PARTS
)


class TestPartsDetection:
    """Tests for wheel parts detection from OpenFOAM boundary file."""

    def test_known_wheel_parts_list(self):
        """Verify known wheel parts list contains expected components."""
        expected_parts = ['rim', 'tire', 'spokes', 'hub', 'disc']
        for part in expected_parts:
            assert any(part in known for known in KNOWN_WHEEL_PARTS), \
                f"Missing known part: {part}"

    def test_detect_parts_from_boundary_with_parts(self, tmp_path):
        """Test detection of parts from a boundary file with named patches."""
        # Create a mock OpenFOAM case structure
        case_dir = tmp_path / "test_case"
        boundary_dir = case_dir / "constant" / "polyMesh"
        boundary_dir.mkdir(parents=True)

        # Create a boundary file with multiple wheel parts
        boundary_content = """FoamFile
{
    version     2.0;
    format      ascii;
    class       polyBoundaryMesh;
    object      boundary;
}

5
(
    inlet
    {
        type            patch;
        nFaces          1000;
        startFace       500000;
    }
    outlet
    {
        type            patch;
        nFaces          1000;
        startFace       501000;
    }
    rim
    {
        type            wall;
        nFaces          5000;
        startFace       502000;
    }
    tire
    {
        type            wall;
        nFaces          8000;
        startFace       507000;
    }
    spokes
    {
        type            wall;
        nFaces          2000;
        startFace       515000;
    }
)
"""
        (boundary_dir / "boundary").write_text(boundary_content)

        parts = detect_wheel_parts(case_dir)

        assert len(parts) >= 3
        assert 'rim' in parts
        assert 'tire' in parts
        assert 'spokes' in parts

    def test_detect_parts_no_parts(self, tmp_path):
        """Test detection returns empty list when no wheel parts found."""
        case_dir = tmp_path / "test_case"
        boundary_dir = case_dir / "constant" / "polyMesh"
        boundary_dir.mkdir(parents=True)

        # Create a boundary file with only 'wheel' patch (no sub-parts)
        boundary_content = """FoamFile
{
    version     2.0;
    format      ascii;
    class       polyBoundaryMesh;
    object      boundary;
}

3
(
    inlet
    {
        type            patch;
        nFaces          1000;
        startFace       500000;
    }
    outlet
    {
        type            patch;
        nFaces          1000;
        startFace       501000;
    }
    wheel
    {
        type            wall;
        nFaces          15000;
        startFace       502000;
    }
)
"""
        (boundary_dir / "boundary").write_text(boundary_content)

        parts = detect_wheel_parts(case_dir)

        # 'wheel' is not in KNOWN_WHEEL_PARTS (only specific parts like rim, tire, etc.)
        assert len(parts) == 0

    def test_detect_parts_missing_boundary_file(self, tmp_path):
        """Test detection returns empty list when boundary file doesn't exist."""
        case_dir = tmp_path / "test_case"
        case_dir.mkdir(parents=True)

        parts = detect_wheel_parts(case_dir)

        assert parts == []


class TestPartsForceExtraction:
    """Tests for per-part force extraction from postProcessing."""

    def test_parse_per_part_forces(self, tmp_path):
        """Test parsing force data from multiple part directories."""
        case_dir = tmp_path / "test_case"

        # Create forceCoeffs directories for each part
        for part in ['rim', 'tire', 'spokes']:
            force_dir = case_dir / "postProcessing" / f"forceCoeffs_{part}" / "0"
            force_dir.mkdir(parents=True)

            # Create forceCoeffs.dat file
            # Format: Time Cm Cd Cl Cl(f) Cl(r)
            force_content = """# Time Cm Cd Cl Cl(f) Cl(r)
0 0.001 0.05 0.001 0.0005 0.0005
100 0.001 0.06 0.001 0.0005 0.0005
200 0.001 0.055 0.001 0.0005 0.0005
"""
            (force_dir / "forceCoeffs.dat").write_text(force_content)

        result = extract_per_part_forces(case_dir)

        assert result['has_parts'] is True
        assert len(result['parts']) == 3

        # Check each part has expected fields
        for part in result['parts']:
            assert 'name' in part
            assert 'Cd' in part
            assert 'Cl' in part
            assert 'Cm' in part
            assert 'drag_percent' in part

    def test_percentage_calculation(self, tmp_path):
        """Test that drag percentages sum to 100%."""
        case_dir = tmp_path / "test_case"

        # Create parts with known Cd values
        cd_values = {'rim': 0.02, 'tire': 0.05, 'spokes': 0.03}  # Total = 0.10

        for part, cd in cd_values.items():
            force_dir = case_dir / "postProcessing" / f"forceCoeffs_{part}" / "0"
            force_dir.mkdir(parents=True)

            force_content = f"""# Time Cm Cd Cl Cl(f) Cl(r)
500 0.001 {cd} 0.001 0.0005 0.0005
"""
            (force_dir / "forceCoeffs.dat").write_text(force_content)

        result = extract_per_part_forces(case_dir)

        assert result['has_parts'] is True

        # Check percentages
        total_percent = sum(p['drag_percent'] for p in result['parts'])
        assert abs(total_percent - 100.0) < 0.1  # Should sum to ~100%

        # Check individual percentages
        for part in result['parts']:
            expected_percent = (cd_values[part['name']] / 0.10) * 100
            assert abs(part['drag_percent'] - expected_percent) < 0.1

    def test_fallback_whole_wheel(self, tmp_path):
        """Test fallback when no per-part data exists."""
        case_dir = tmp_path / "test_case"
        case_dir.mkdir(parents=True)

        # Only create the main forceCoeffs directory (no _partname suffix)
        force_dir = case_dir / "postProcessing" / "forceCoeffs" / "0"
        force_dir.mkdir(parents=True)

        force_content = """# Time Cm Cd Cl Cl(f) Cl(r)
500 0.001 0.15 0.001 0.0005 0.0005
"""
        (force_dir / "forceCoeffs.dat").write_text(force_content)

        result = extract_per_part_forces(case_dir)

        # Should return has_parts=False since no forceCoeffs_* dirs
        assert result['has_parts'] is False
        assert len(result['parts']) == 0


class TestPerPartForceCoeffsGeneration:
    """Tests for generating per-part forceCoeffs entries."""

    def test_generate_per_part_force_coeffs(self):
        """Test generation of forceCoeffs entries for multiple parts."""
        parts = ['rim', 'tire', 'spokes']
        config = {
            'air': {'rho': 1.225},
            'speed': 13.9,
            'wheel_radius': 0.325,
            'aref': 0.0225,
            'yaw_angles': [0]
        }

        result = generate_per_part_force_coeffs(parts, config)

        # Check each part has an entry
        assert 'forceCoeffs_rim' in result
        assert 'forceCoeffs_tire' in result
        assert 'forceCoeffs_spokes' in result

        # Check required fields are present
        assert 'patches' in result
        assert 'rhoInf' in result
        assert 'magUInf' in result
        assert 'Aref' in result

    def test_generate_per_part_force_coeffs_empty_list(self):
        """Test generation with empty parts list returns empty string."""
        result = generate_per_part_force_coeffs([], {})
        assert result == ""

    def test_generate_per_part_force_coeffs_with_yaw(self):
        """Test drag direction is adjusted for yaw angle."""
        parts = ['rim']
        config = {
            'air': {'rho': 1.225},
            'speed': 13.9,
            'wheel_radius': 0.325,
            'aref': 0.0225,
            'yaw_angles': [15]  # 15 degree yaw
        }

        result = generate_per_part_force_coeffs(parts, config)

        # Drag direction should be adjusted for 15 degree yaw
        # cos(15) ≈ 0.966, sin(15) ≈ 0.259
        assert 'dragDir' in result
        # The x component should be ~0.966, y ~0.259
        assert '0.9' in result  # Approximate check


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
