"""
STL File Validation Module for WheelFlow

Provides comprehensive validation of STL files with detailed error messages
to help users diagnose and fix common issues.
"""

import struct
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum


class STLFormat(Enum):
    BINARY = "binary"
    ASCII = "ascii"
    UNKNOWN = "unknown"


class ValidationSeverity(Enum):
    ERROR = "error"      # File cannot be used
    WARNING = "warning"  # File may cause issues
    INFO = "info"        # Informational


@dataclass
class ValidationIssue:
    severity: ValidationSeverity
    code: str
    message: str
    details: Optional[str] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "suggestion": self.suggestion
        }


@dataclass
class STLGeometry:
    """Parsed STL geometry information"""
    triangle_count: int = 0
    vertex_count: int = 0
    bounds_min: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    bounds_max: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    center: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    dimensions: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    @property
    def max_dimension(self) -> float:
        return max(self.dimensions)

    @property
    def min_dimension(self) -> float:
        return min(d for d in self.dimensions if d > 0) if any(d > 0 for d in self.dimensions) else 0.0


@dataclass
class STLValidationResult:
    """Complete validation result for an STL file"""
    valid: bool
    format: STLFormat
    geometry: Optional[STLGeometry] = None
    issues: List[ValidationIssue] = field(default_factory=list)
    file_size: int = 0
    header: str = ""

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "format": self.format.value,
            "geometry": {
                "triangles": self.geometry.triangle_count if self.geometry else 0,
                "bounds": {
                    "min": list(self.geometry.bounds_min) if self.geometry else [0, 0, 0],
                    "max": list(self.geometry.bounds_max) if self.geometry else [0, 0, 0]
                },
                "center": list(self.geometry.center) if self.geometry else [0, 0, 0],
                "dimensions": list(self.geometry.dimensions) if self.geometry else [0, 0, 0]
            } if self.geometry else None,
            "issues": [i.to_dict() for i in self.issues],
            "file_size": self.file_size,
            "header": self.header
        }

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    @property
    def error_message(self) -> Optional[str]:
        """Get combined error message for API responses"""
        if not self.errors:
            return None
        messages = [f"{e.message}" for e in self.errors]
        if len(messages) == 1:
            error = self.errors[0]
            msg = error.message
            if error.suggestion:
                msg += f" {error.suggestion}"
            return msg
        return "Multiple issues found: " + "; ".join(messages)


class STLValidator:
    """
    Validates STL files for use with OpenFOAM CFD simulations.

    Checks for:
    - File format (binary vs ASCII)
    - Binary STL header issues (solid keyword confusion)
    - File integrity (expected vs actual size)
    - Geometry bounds and scale
    - Degenerate triangles
    - OpenFOAM compatibility
    """

    # Size limits
    MIN_FILE_SIZE = 84  # Minimum binary STL: 80 header + 4 triangle count
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB

    # Triangle limits
    MIN_TRIANGLES = 4  # Minimum for a closed surface (tetrahedron)
    MAX_TRIANGLES = 10_000_000  # 10 million triangles

    # Geometry limits (in meters, assuming SI units)
    MIN_DIMENSION_M = 0.001  # 1 mm
    MAX_DIMENSION_M = 100.0  # 100 m
    LIKELY_MM_THRESHOLD = 10.0  # If max dimension > 10, likely in mm

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        self.result = STLValidationResult(
            valid=True,
            format=STLFormat.UNKNOWN,
            file_size=0
        )

    def validate(self) -> STLValidationResult:
        """Run all validation checks and return result"""
        try:
            self._check_file_exists()
            self._check_file_size()
            self._detect_format()
            self._parse_geometry()
            self._check_geometry_scale()
            self._check_openfoam_compatibility()
        except Exception as e:
            self._add_issue(
                ValidationSeverity.ERROR,
                "PARSE_ERROR",
                f"Failed to parse STL file: {str(e)}",
                details=str(type(e).__name__)
            )
            self.result.valid = False

        # Set valid=False if there are any errors
        if self.result.errors:
            self.result.valid = False

        return self.result

    def _add_issue(self, severity: ValidationSeverity, code: str, message: str,
                   details: str = None, suggestion: str = None):
        self.result.issues.append(ValidationIssue(
            severity=severity,
            code=code,
            message=message,
            details=details,
            suggestion=suggestion
        ))

    def _check_file_exists(self):
        if not self.file_path.exists():
            self._add_issue(
                ValidationSeverity.ERROR,
                "FILE_NOT_FOUND",
                f"STL file not found: {self.file_path.name}",
                suggestion="Please upload a valid STL file."
            )
            raise FileNotFoundError(self.file_path)

    def _check_file_size(self):
        self.result.file_size = self.file_path.stat().st_size

        if self.result.file_size < self.MIN_FILE_SIZE:
            self._add_issue(
                ValidationSeverity.ERROR,
                "FILE_TOO_SMALL",
                f"STL file is too small ({self.result.file_size} bytes)",
                details=f"Minimum size is {self.MIN_FILE_SIZE} bytes",
                suggestion="The file may be empty or corrupted. Please re-export from your CAD software."
            )

        if self.result.file_size > self.MAX_FILE_SIZE:
            size_mb = self.result.file_size / (1024 * 1024)
            self._add_issue(
                ValidationSeverity.ERROR,
                "FILE_TOO_LARGE",
                f"STL file is too large ({size_mb:.1f} MB)",
                details=f"Maximum size is {self.MAX_FILE_SIZE // (1024*1024)} MB",
                suggestion="Please simplify the mesh or reduce triangle count in your CAD software."
            )

    def _detect_format(self):
        """Detect if STL is binary or ASCII and check for header issues"""
        with open(self.file_path, 'rb') as f:
            header = f.read(80)
            self.result.header = header.decode('ascii', errors='replace').strip('\x00').strip()

            # Read potential triangle count
            triangle_bytes = f.read(4)
            if len(triangle_bytes) < 4:
                self._add_issue(
                    ValidationSeverity.ERROR,
                    "TRUNCATED_FILE",
                    "STL file appears to be truncated",
                    suggestion="Please re-export the file from your CAD software."
                )
                return

            potential_triangles = struct.unpack('<I', triangle_bytes)[0]

            # Calculate expected binary file size
            # 80 header + 4 count + (50 bytes per triangle)
            expected_binary_size = 80 + 4 + (potential_triangles * 50)

            # Check if it matches binary format
            if self.result.file_size == expected_binary_size:
                self.result.format = STLFormat.BINARY

                # Check for the problematic "solid" header in binary STL
                if header.lower().startswith(b'solid'):
                    self._add_issue(
                        ValidationSeverity.ERROR,
                        "BINARY_SOLID_HEADER",
                        "Binary STL file has header starting with 'solid'",
                        details=f"Header: '{self.result.header[:50]}...'",
                        suggestion="This confuses OpenFOAM's ASCII/binary detection. "
                                   "The file will be automatically fixed during processing."
                    )
                    # Mark as fixable - not a fatal error if we fix it
                    self.result.issues[-1].severity = ValidationSeverity.WARNING
            else:
                # Try ASCII detection
                f.seek(0)
                try:
                    content_start = f.read(1000).decode('ascii')
                    if 'facet normal' in content_start.lower() or 'vertex' in content_start.lower():
                        self.result.format = STLFormat.ASCII
                    else:
                        # Size mismatch and not ASCII
                        self._add_issue(
                            ValidationSeverity.ERROR,
                            "INVALID_FORMAT",
                            "STL file format could not be determined",
                            details=f"Expected size for {potential_triangles} triangles: {expected_binary_size}, "
                                    f"actual: {self.result.file_size}",
                            suggestion="The file may be corrupted. Please re-export from your CAD software."
                        )
                except UnicodeDecodeError:
                    # Binary content that doesn't match expected size
                    self._add_issue(
                        ValidationSeverity.ERROR,
                        "CORRUPTED_BINARY",
                        "Binary STL file appears corrupted",
                        details=f"Expected {expected_binary_size} bytes, got {self.result.file_size}",
                        suggestion="Please re-export the file from your CAD software."
                    )

    def _parse_geometry(self):
        """Parse geometry information from the STL file"""
        if self.result.format == STLFormat.BINARY:
            self._parse_binary_geometry()
        elif self.result.format == STLFormat.ASCII:
            self._parse_ascii_geometry()

    def _parse_binary_geometry(self):
        """Parse binary STL geometry"""
        geometry = STLGeometry()

        with open(self.file_path, 'rb') as f:
            f.seek(80)  # Skip header
            triangle_count = struct.unpack('<I', f.read(4))[0]
            geometry.triangle_count = triangle_count
            geometry.vertex_count = triangle_count * 3

            if triangle_count < self.MIN_TRIANGLES:
                self._add_issue(
                    ValidationSeverity.ERROR,
                    "TOO_FEW_TRIANGLES",
                    f"STL has only {triangle_count} triangles",
                    details=f"Minimum is {self.MIN_TRIANGLES} for a closed surface",
                    suggestion="The geometry may be incomplete or degenerate."
                )

            if triangle_count > self.MAX_TRIANGLES:
                self._add_issue(
                    ValidationSeverity.WARNING,
                    "MANY_TRIANGLES",
                    f"STL has {triangle_count:,} triangles",
                    details="Large meshes may slow down simulation setup",
                    suggestion="Consider simplifying the mesh if simulation takes too long."
                )

            # Calculate bounds by reading all vertices
            min_coords = [float('inf')] * 3
            max_coords = [float('-inf')] * 3

            for _ in range(triangle_count):
                f.read(12)  # Skip normal vector
                for _ in range(3):  # 3 vertices per triangle
                    vertex = struct.unpack('<3f', f.read(12))
                    for i in range(3):
                        min_coords[i] = min(min_coords[i], vertex[i])
                        max_coords[i] = max(max_coords[i], vertex[i])
                f.read(2)  # Skip attribute byte count

            geometry.bounds_min = tuple(min_coords)
            geometry.bounds_max = tuple(max_coords)
            geometry.dimensions = tuple(max_coords[i] - min_coords[i] for i in range(3))
            geometry.center = tuple((max_coords[i] + min_coords[i]) / 2 for i in range(3))

        self.result.geometry = geometry

    def _parse_ascii_geometry(self):
        """Parse ASCII STL geometry"""
        geometry = STLGeometry()
        min_coords = [float('inf')] * 3
        max_coords = [float('-inf')] * 3
        triangle_count = 0
        vertex_count = 0

        with open(self.file_path, 'r', errors='replace') as f:
            for line in f:
                line_lower = line.lower().strip()
                if line_lower.startswith('vertex'):
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            vertex = [float(parts[1]), float(parts[2]), float(parts[3])]
                            vertex_count += 1
                            for i in range(3):
                                min_coords[i] = min(min_coords[i], vertex[i])
                                max_coords[i] = max(max_coords[i], vertex[i])
                        except ValueError:
                            pass
                elif 'endfacet' in line_lower:
                    triangle_count += 1

        geometry.triangle_count = triangle_count
        geometry.vertex_count = vertex_count

        if triangle_count > 0:
            geometry.bounds_min = tuple(min_coords)
            geometry.bounds_max = tuple(max_coords)
            geometry.dimensions = tuple(max_coords[i] - min_coords[i] for i in range(3))
            geometry.center = tuple((max_coords[i] + min_coords[i]) / 2 for i in range(3))

        self.result.geometry = geometry

    def _check_geometry_scale(self):
        """Check if geometry scale is appropriate for CFD"""
        if not self.result.geometry:
            return

        geom = self.result.geometry
        max_dim = geom.max_dimension
        min_dim = geom.min_dimension

        # Check if geometry appears to be in millimeters
        if max_dim > self.LIKELY_MM_THRESHOLD:
            self._add_issue(
                ValidationSeverity.WARNING,
                "LIKELY_MILLIMETERS",
                f"Geometry dimensions suggest millimeters (max: {max_dim:.1f})",
                details=f"Dimensions: {geom.dimensions[0]:.1f} x {geom.dimensions[1]:.1f} x {geom.dimensions[2]:.1f}",
                suggestion="OpenFOAM uses SI units (meters). The geometry will be automatically scaled."
            )

        # Check for extremely small geometry
        if max_dim < self.MIN_DIMENSION_M and max_dim > 0:
            self._add_issue(
                ValidationSeverity.WARNING,
                "VERY_SMALL_GEOMETRY",
                f"Geometry is very small (max dimension: {max_dim*1000:.3f} mm)",
                suggestion="Ensure the units are correct. Very small features may not mesh well."
            )

        # Check for extremely large geometry
        if max_dim > self.MAX_DIMENSION_M:
            self._add_issue(
                ValidationSeverity.WARNING,
                "VERY_LARGE_GEOMETRY",
                f"Geometry is very large (max dimension: {max_dim:.1f} m)",
                suggestion="Ensure the units are correct. Large domains require more computational resources."
            )

        # Check for flat/degenerate geometry
        if min_dim > 0 and max_dim / min_dim > 1000:
            self._add_issue(
                ValidationSeverity.WARNING,
                "HIGH_ASPECT_RATIO",
                f"Geometry has very high aspect ratio ({max_dim/min_dim:.0f}:1)",
                details=f"Dimensions: {geom.dimensions[0]:.4f} x {geom.dimensions[1]:.4f} x {geom.dimensions[2]:.4f}",
                suggestion="This may cause meshing difficulties. Consider the geometry orientation."
            )

    def _check_openfoam_compatibility(self):
        """Check for OpenFOAM-specific compatibility issues"""
        if not self.result.geometry:
            return

        # Check triangle count for snappyHexMesh
        if self.result.geometry.triangle_count > 1_000_000:
            self._add_issue(
                ValidationSeverity.INFO,
                "LARGE_SURFACE_MESH",
                f"Surface has {self.result.geometry.triangle_count:,} triangles",
                suggestion="snappyHexMesh may take longer. Consider using 'basic' quality for initial tests."
            )


def validate_stl_file(file_path: Path) -> STLValidationResult:
    """
    Convenience function to validate an STL file.

    Args:
        file_path: Path to the STL file

    Returns:
        STLValidationResult with validation status and any issues found
    """
    validator = STLValidator(file_path)
    return validator.validate()


def fix_binary_stl_header(file_path: Path, backup: bool = True) -> bool:
    """
    Fix a binary STL file that has a header starting with 'solid'.

    This is a common issue where CAD software exports binary STL files
    with headers like "solid <model_name>" which confuses OpenFOAM's
    ASCII/binary detection.

    Args:
        file_path: Path to the STL file
        backup: If True, create a .backup file before modifying

    Returns:
        True if the file was modified, False if no changes needed
    """
    file_path = Path(file_path)

    with open(file_path, 'rb') as f:
        header = f.read(80)

        # Check if fix is needed
        if not header.lower().startswith(b'solid'):
            return False

        # Verify it's actually binary (not ASCII)
        triangle_bytes = f.read(4)
        if len(triangle_bytes) < 4:
            return False

        potential_triangles = struct.unpack('<I', triangle_bytes)[0]
        expected_size = 80 + 4 + (potential_triangles * 50)

        if file_path.stat().st_size != expected_size:
            return False  # Not a binary STL

        # Read rest of file
        f.seek(0)
        content = bytearray(f.read())

    # Create backup if requested
    if backup:
        backup_path = file_path.with_suffix(file_path.suffix + '.backup')
        with open(backup_path, 'wb') as f:
            f.write(content)

    # Replace header
    new_header = b"binary STL - header fixed for OpenFOAM compatibility"
    content[0:80] = new_header.ljust(80, b'\x00')

    # Write fixed file
    with open(file_path, 'wb') as f:
        f.write(content)

    return True


def detect_stl_units(geometry: STLGeometry) -> str:
    """
    Attempt to detect the units of an STL file based on geometry dimensions.

    For a bicycle wheel:
    - In meters: diameter ~0.6-0.7m
    - In millimeters: diameter ~600-700mm
    - In inches: diameter ~24-28in

    Args:
        geometry: Parsed STL geometry

    Returns:
        Detected unit string: 'meters', 'millimeters', 'inches', or 'unknown'
    """
    max_dim = geometry.max_dimension

    # Typical bicycle wheel diameter ranges
    if 0.5 <= max_dim <= 0.8:
        return 'meters'
    elif 500 <= max_dim <= 800:
        return 'millimeters'
    elif 20 <= max_dim <= 32:
        return 'inches'
    elif max_dim < 0.1:
        return 'meters'  # Small part in meters
    elif max_dim > 100:
        return 'millimeters'  # Likely mm

    return 'unknown'


def transform_stl_for_openfoam(src_path: Path, dst_path: Path,
                                scale: float = 0.001,
                                center: bool = True,
                                stand_upright: bool = True) -> dict:
    """
    Transform a binary STL file for use with OpenFOAM.

    Applies scaling (mm->m), centering, and rotation to stand the wheel
    upright on the ground plane (z=0).

    Args:
        src_path: Source STL file path
        dst_path: Destination STL file path
        scale: Scale factor (default 0.001 for mm->m)
        center: Center geometry at origin in X-Y
        stand_upright: Rotate wheel to stand upright, place on ground

    Returns:
        Dictionary with transformation info
    """
    src_path = Path(src_path)
    dst_path = Path(dst_path)

    with open(src_path, 'rb') as f:
        header = f.read(80)
        num_triangles = struct.unpack('<I', f.read(4))[0]

        # First pass: read all data and calculate bounds
        triangles = []
        sum_x = sum_y = sum_z = 0
        count = 0
        min_coords = [float('inf')] * 3
        max_coords = [float('-inf')] * 3

        for _ in range(num_triangles):
            normal = struct.unpack('<3f', f.read(12))
            verts = [struct.unpack('<3f', f.read(12)) for _ in range(3)]
            attr = struct.unpack('<H', f.read(2))[0]
            triangles.append((normal, verts, attr))

            for v in verts:
                sum_x += v[0]
                sum_y += v[1]
                sum_z += v[2]
                count += 1
                for i in range(3):
                    min_coords[i] = min(min_coords[i], v[i])
                    max_coords[i] = max(max_coords[i], v[i])

    # Calculate center and dimensions in original units
    cx = sum_x / count
    cy = sum_y / count
    cz = sum_z / count
    dims = [max_coords[i] - min_coords[i] for i in range(3)]

    # Determine wheel radius (after scaling)
    # Assume largest dimension in X-Y plane is the diameter
    wheel_diameter = max(dims[0], dims[1]) * scale
    wheel_radius = wheel_diameter / 2

    def transform_vertex(v):
        x, y, z = v
        # Center
        if center:
            x -= cx
            y -= cy
            z -= cz
        # Scale
        x *= scale
        y *= scale
        z *= scale
        # Rotate to stand upright (rotate 90° around X axis: Y->Z, Z->-Y)
        if stand_upright:
            x, y, z = x, -z, y
            # Lift so bottom touches ground (z=0)
            z += wheel_radius
        return (x, y, z)

    def transform_normal(n):
        if stand_upright:
            return (n[0], -n[2], n[1])
        return n

    # Write transformed STL
    with open(dst_path, 'wb') as f:
        # Write header (not starting with 'solid')
        new_header = b"binary STL - transformed for OpenFOAM CFD"
        f.write(new_header.ljust(80, b'\x00'))
        f.write(struct.pack('<I', num_triangles))

        for normal, verts, attr in triangles:
            # Transform and write normal
            tn = transform_normal(normal)
            f.write(struct.pack('<3f', *tn))
            # Transform and write vertices
            for v in verts:
                tv = transform_vertex(v)
                f.write(struct.pack('<3f', *tv))
            f.write(struct.pack('<H', attr))

    return {
        'original_center': (cx, cy, cz),
        'original_dimensions': dims,
        'scale': scale,
        'wheel_radius': wheel_radius,
        'wheel_diameter': wheel_diameter,
        'final_dimensions': [d * scale for d in dims]
    }


def get_stl_transform_for_openfoam(geometry: STLGeometry,
                                    target_unit: str = 'meters',
                                    center_origin: bool = True,
                                    stand_upright: bool = True) -> dict:
    """
    Calculate transformation parameters to prepare STL for OpenFOAM.

    Args:
        geometry: Parsed STL geometry
        target_unit: Target unit system ('meters')
        center_origin: If True, center geometry at origin
        stand_upright: If True, orient wheel to stand on ground (Z=0)

    Returns:
        Dictionary with transformation parameters
    """
    detected_unit = detect_stl_units(geometry)

    # Calculate scale factor
    scale = 1.0
    if detected_unit == 'millimeters':
        scale = 0.001
    elif detected_unit == 'inches':
        scale = 0.0254

    # Calculate translation
    translation = [0.0, 0.0, 0.0]
    if center_origin:
        translation = [-c * scale for c in geometry.center]

    # For wheel standing upright, add half the diameter to Z
    wheel_radius = 0.0
    if stand_upright:
        # Assume the largest dimension in X-Y plane is the diameter
        scaled_dims = [d * scale for d in geometry.dimensions]
        wheel_radius = max(scaled_dims[0], scaled_dims[1]) / 2
        translation[2] += wheel_radius

    return {
        'detected_unit': detected_unit,
        'scale': scale,
        'translation': translation,
        'wheel_radius': wheel_radius,
        'final_dimensions': [d * scale for d in geometry.dimensions]
    }
