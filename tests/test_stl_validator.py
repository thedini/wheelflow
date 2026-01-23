"""
Unit tests for STL validation module
"""

import pytest
import struct
from pathlib import Path

from stl_validator import (
    STLValidator,
    STLFormat,
    ValidationSeverity,
    validate_stl_file,
    fix_binary_stl_header,
    detect_stl_units,
    get_stl_transform_for_openfoam,
    STLGeometry
)


class TestSTLFormatDetection:
    """Tests for STL format detection (binary vs ASCII)"""

    def test_detect_valid_binary_stl(self, valid_binary_stl):
        """Valid binary STL should be detected correctly"""
        result = validate_stl_file(valid_binary_stl)

        assert result.format == STLFormat.BINARY
        assert result.valid is True

    def test_detect_valid_ascii_stl(self, valid_ascii_stl):
        """Valid ASCII STL should be detected correctly"""
        result = validate_stl_file(valid_ascii_stl)

        assert result.format == STLFormat.ASCII
        assert result.valid is True

    def test_detect_binary_with_solid_header(self, binary_stl_solid_header):
        """Binary STL with 'solid' header should be detected with warning"""
        result = validate_stl_file(binary_stl_solid_header)

        assert result.format == STLFormat.BINARY
        # Should have a warning about the header
        warning_codes = [w.code for w in result.warnings]
        assert "BINARY_SOLID_HEADER" in warning_codes

    def test_truncated_file_detected(self, truncated_stl):
        """Truncated STL should be detected as corrupted"""
        result = validate_stl_file(truncated_stl)

        assert result.valid is False
        error_codes = [e.code for e in result.errors]
        assert any(code in ["CORRUPTED_BINARY", "INVALID_FORMAT"] for code in error_codes)

    def test_empty_file_rejected(self, empty_file):
        """Empty file should be rejected"""
        result = validate_stl_file(empty_file)

        assert result.valid is False
        error_codes = [e.code for e in result.errors]
        assert "FILE_TOO_SMALL" in error_codes


class TestSTLGeometryParsing:
    """Tests for STL geometry extraction"""

    def test_binary_geometry_parsing(self, valid_binary_stl):
        """Binary STL geometry should be parsed correctly"""
        result = validate_stl_file(valid_binary_stl)

        assert result.geometry is not None
        assert result.geometry.triangle_count == 4  # tetrahedron
        assert result.geometry.vertex_count == 12  # 4 triangles * 3 vertices

    def test_ascii_geometry_parsing(self, valid_ascii_stl):
        """ASCII STL geometry should be parsed correctly"""
        result = validate_stl_file(valid_ascii_stl)

        assert result.geometry is not None
        assert result.geometry.triangle_count == 4

    def test_bounds_calculation(self, valid_binary_stl):
        """Bounding box should be calculated correctly"""
        result = validate_stl_file(valid_binary_stl)

        # Tetrahedron vertices: (0,0,0), (1,0,0), (0.5,1,0), (0.5,0.5,1)
        assert result.geometry.bounds_min[0] == pytest.approx(0.0, abs=0.01)
        assert result.geometry.bounds_max[0] == pytest.approx(1.0, abs=0.01)
        assert result.geometry.bounds_max[2] == pytest.approx(1.0, abs=0.01)

    def test_dimensions_calculation(self, valid_binary_stl):
        """Dimensions should be calculated correctly"""
        result = validate_stl_file(valid_binary_stl)

        dims = result.geometry.dimensions
        assert dims[0] == pytest.approx(1.0, abs=0.01)  # X dimension
        assert dims[1] == pytest.approx(1.0, abs=0.01)  # Y dimension
        assert dims[2] == pytest.approx(1.0, abs=0.01)  # Z dimension

    def test_center_calculation(self, valid_binary_stl):
        """Center should be calculated correctly"""
        result = validate_stl_file(valid_binary_stl)

        center = result.geometry.center
        assert center[0] == pytest.approx(0.5, abs=0.01)
        assert center[1] == pytest.approx(0.5, abs=0.01)
        assert center[2] == pytest.approx(0.5, abs=0.01)


class TestRealWheelSTL:
    """Tests using the real wheel STL file"""

    def test_wheel_stl_detection(self, wheel_stl_path):
        """Real wheel STL should be validated with appropriate warnings"""
        if not wheel_stl_path.exists():
            pytest.skip("Wheel STL fixture not available")

        result = validate_stl_file(wheel_stl_path)

        # File should be detected as binary
        assert result.format == STLFormat.BINARY

        # Should have the solid header warning
        warning_codes = [w.code for w in result.warnings]
        assert "BINARY_SOLID_HEADER" in warning_codes

    def test_wheel_geometry(self, wheel_stl_path):
        """Wheel geometry should be parsed correctly"""
        if not wheel_stl_path.exists():
            pytest.skip("Wheel STL fixture not available")

        result = validate_stl_file(wheel_stl_path)

        assert result.geometry is not None
        assert result.geometry.triangle_count == 94128

        # Dimensions should indicate millimeters
        max_dim = result.geometry.max_dimension
        assert max_dim > 600  # ~633mm diameter
        assert max_dim < 700

    def test_wheel_units_detection(self, wheel_stl_path):
        """Wheel units should be detected as millimeters"""
        if not wheel_stl_path.exists():
            pytest.skip("Wheel STL fixture not available")

        result = validate_stl_file(wheel_stl_path)
        units = detect_stl_units(result.geometry)

        assert units == "millimeters"

    def test_wheel_scale_warning(self, wheel_stl_path):
        """Wheel should trigger millimeter scale warning"""
        if not wheel_stl_path.exists():
            pytest.skip("Wheel STL fixture not available")

        result = validate_stl_file(wheel_stl_path)

        warning_codes = [w.code for w in result.warnings]
        assert "LIKELY_MILLIMETERS" in warning_codes


class TestHeaderFix:
    """Tests for fixing binary STL headers"""

    def test_fix_solid_header(self, binary_stl_solid_header, temp_dir):
        """Fixing solid header should work correctly"""
        import shutil

        # Copy to temp location
        test_file = temp_dir / "to_fix.stl"
        shutil.copy(binary_stl_solid_header, test_file)

        # Verify header starts with solid
        with open(test_file, 'rb') as f:
            header = f.read(80)
        assert header.lower().startswith(b'solid')

        # Fix the header
        was_fixed = fix_binary_stl_header(test_file, backup=True)

        assert was_fixed is True

        # Verify header was changed
        with open(test_file, 'rb') as f:
            new_header = f.read(80)
        assert not new_header.lower().startswith(b'solid')

        # Verify backup was created
        assert (temp_dir / "to_fix.stl.backup").exists()

        # Verify file still validates
        result = validate_stl_file(test_file)
        assert result.format == STLFormat.BINARY
        # Should not have the solid header warning anymore
        warning_codes = [w.code for w in result.warnings]
        assert "BINARY_SOLID_HEADER" not in warning_codes

    def test_no_fix_needed_for_valid_header(self, valid_binary_stl, temp_dir):
        """Files with valid headers should not be modified"""
        import shutil

        test_file = temp_dir / "already_valid.stl"
        shutil.copy(valid_binary_stl, test_file)

        was_fixed = fix_binary_stl_header(test_file)

        assert was_fixed is False

    def test_no_fix_for_ascii(self, valid_ascii_stl, temp_dir):
        """ASCII STL files should not be modified"""
        import shutil

        test_file = temp_dir / "ascii.stl"
        shutil.copy(valid_ascii_stl, test_file)

        was_fixed = fix_binary_stl_header(test_file)

        assert was_fixed is False


class TestUnitsDetection:
    """Tests for STL unit detection"""

    def test_detect_meters(self):
        """Geometry in meters should be detected"""
        geom = STLGeometry(
            bounds_min=(0, 0, 0),
            bounds_max=(0.633, 0.633, 0.034),
            dimensions=(0.633, 0.633, 0.034)
        )
        assert detect_stl_units(geom) == "meters"

    def test_detect_millimeters(self, millimeter_stl):
        """Geometry in millimeters should be detected"""
        result = validate_stl_file(millimeter_stl)
        units = detect_stl_units(result.geometry)
        assert units == "millimeters"

    def test_detect_inches(self):
        """Geometry in inches should be detected"""
        geom = STLGeometry(
            bounds_min=(0, 0, 0),
            bounds_max=(26, 26, 1.5),  # ~26 inch wheel
            dimensions=(26, 26, 1.5)
        )
        assert detect_stl_units(geom) == "inches"


class TestTransformCalculation:
    """Tests for OpenFOAM transform calculation"""

    def test_millimeter_transform(self, millimeter_stl):
        """Millimeter geometry should get 0.001 scale factor"""
        result = validate_stl_file(millimeter_stl)
        transform = get_stl_transform_for_openfoam(result.geometry)

        assert transform['detected_unit'] == 'millimeters'
        assert transform['scale'] == 0.001

    def test_meter_transform(self, valid_binary_stl):
        """Meter geometry should get 1.0 scale factor"""
        result = validate_stl_file(valid_binary_stl)
        transform = get_stl_transform_for_openfoam(result.geometry)

        assert transform['scale'] == 1.0

    def test_centering_translation(self, millimeter_stl):
        """Translation should center geometry at origin"""
        result = validate_stl_file(millimeter_stl)
        transform = get_stl_transform_for_openfoam(
            result.geometry,
            center_origin=True,
            stand_upright=False
        )

        # After scaling and translation, center should be at origin
        scaled_center = [c * transform['scale'] for c in result.geometry.center]
        final_center = [scaled_center[i] + transform['translation'][i] for i in range(3)]

        for coord in final_center:
            assert coord == pytest.approx(0.0, abs=0.001)


class TestValidationResult:
    """Tests for ValidationResult functionality"""

    def test_error_message_single(self, empty_file):
        """Single error should produce clear message"""
        result = validate_stl_file(empty_file)

        assert result.error_message is not None
        assert "too small" in result.error_message.lower()

    def test_to_dict(self, valid_binary_stl):
        """Result should convert to dictionary correctly"""
        result = validate_stl_file(valid_binary_stl)
        d = result.to_dict()

        assert 'valid' in d
        assert 'format' in d
        assert 'geometry' in d
        assert 'issues' in d
        assert d['valid'] is True
        assert d['format'] == 'binary'

    def test_warnings_vs_errors(self, binary_stl_solid_header):
        """Warnings should not make file invalid"""
        result = validate_stl_file(binary_stl_solid_header)

        assert len(result.warnings) > 0
        assert len(result.errors) == 0
        # File is still valid despite warnings
        # (Note: BINARY_SOLID_HEADER is a warning, not error)


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    def test_nonexistent_file(self, temp_dir):
        """Non-existent file should produce clear error"""
        result = validate_stl_file(temp_dir / "does_not_exist.stl")

        assert result.valid is False
        error_codes = [e.code for e in result.errors]
        assert "FILE_NOT_FOUND" in error_codes

    def test_very_small_triangle_count(self, temp_dir):
        """File with too few triangles should warn"""
        stl_path = temp_dir / "one_triangle.stl"

        with open(stl_path, 'wb') as f:
            f.write(b"binary STL".ljust(80, b'\x00'))
            f.write(struct.pack('<I', 1))  # Just 1 triangle
            f.write(struct.pack('<3f', 0, 0, 1))  # normal
            f.write(struct.pack('<3f', 0, 0, 0))  # v1
            f.write(struct.pack('<3f', 1, 0, 0))  # v2
            f.write(struct.pack('<3f', 0, 1, 0))  # v3
            f.write(struct.pack('<H', 0))

        result = validate_stl_file(stl_path)

        error_codes = [e.code for e in result.errors]
        assert "TOO_FEW_TRIANGLES" in error_codes


class TestIssueMessages:
    """Tests for issue message quality"""

    def test_issues_have_suggestions(self, binary_stl_solid_header):
        """Issues should include helpful suggestions"""
        result = validate_stl_file(binary_stl_solid_header)

        for issue in result.issues:
            # All issues should have suggestions
            assert issue.suggestion is not None
            assert len(issue.suggestion) > 10

    def test_error_message_mentions_cad(self, truncated_stl):
        """Error messages should mention CAD software for export issues"""
        result = validate_stl_file(truncated_stl)

        # At least one suggestion should mention re-exporting
        suggestions = [i.suggestion for i in result.issues if i.suggestion]
        combined = " ".join(suggestions).lower()
        assert "export" in combined or "cad" in combined
