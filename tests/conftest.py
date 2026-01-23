"""
Pytest configuration and fixtures for WheelFlow tests
"""

import pytest
import struct
import tempfile
import shutil
from pathlib import Path

# Add backend to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def wheel_stl_path(fixtures_dir):
    """Path to the real wheel STL file with 'solid' header issue"""
    return fixtures_dir / "wheel_binary_solid_header.stl"


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs"""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def valid_binary_stl(temp_dir):
    """Create a minimal valid binary STL file (a tetrahedron)"""
    stl_path = temp_dir / "valid_binary.stl"

    # A tetrahedron has 4 triangular faces
    vertices = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.5, 1.0, 0.0),
        (0.5, 0.5, 1.0)
    ]

    # 4 triangular faces
    faces = [
        (0, 1, 2),  # base
        (0, 1, 3),  # front
        (1, 2, 3),  # right
        (2, 0, 3),  # left
    ]

    with open(stl_path, 'wb') as f:
        # Header (80 bytes) - NOT starting with "solid"
        header = b"binary STL - test tetrahedron"
        f.write(header.ljust(80, b'\x00'))

        # Number of triangles
        f.write(struct.pack('<I', len(faces)))

        # Write each triangle
        for face in faces:
            # Normal vector (we'll use zeros, not strictly correct but valid)
            f.write(struct.pack('<3f', 0.0, 0.0, 0.0))

            # Three vertices
            for vertex_idx in face:
                f.write(struct.pack('<3f', *vertices[vertex_idx]))

            # Attribute byte count
            f.write(struct.pack('<H', 0))

    return stl_path


@pytest.fixture
def binary_stl_solid_header(temp_dir):
    """Create a binary STL with 'solid' header (the problematic case)"""
    stl_path = temp_dir / "binary_solid_header.stl"

    vertices = [
        (0.0, 0.0, 0.0),
        (100.0, 0.0, 0.0),
        (50.0, 100.0, 0.0),
        (50.0, 50.0, 100.0)
    ]

    faces = [
        (0, 1, 2),
        (0, 1, 3),
        (1, 2, 3),
        (2, 0, 3),
    ]

    with open(stl_path, 'wb') as f:
        # Header starting with "solid" - THIS IS THE PROBLEM
        header = b"solid TestModel - exported from CAD"
        f.write(header.ljust(80, b'\x00'))

        f.write(struct.pack('<I', len(faces)))

        for face in faces:
            f.write(struct.pack('<3f', 0.0, 0.0, 0.0))
            for vertex_idx in face:
                f.write(struct.pack('<3f', *vertices[vertex_idx]))
            f.write(struct.pack('<H', 0))

    return stl_path


@pytest.fixture
def valid_ascii_stl(temp_dir):
    """Create a valid ASCII STL file"""
    stl_path = temp_dir / "valid_ascii.stl"

    content = """solid test
  facet normal 0 0 -1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 0.5 1 0
    endloop
  endfacet
  facet normal 0 -1 0
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 0.5 0.5 1
    endloop
  endfacet
  facet normal 1 0 0
    outer loop
      vertex 1 0 0
      vertex 0.5 1 0
      vertex 0.5 0.5 1
    endloop
  endfacet
  facet normal -1 0 0
    outer loop
      vertex 0.5 1 0
      vertex 0 0 0
      vertex 0.5 0.5 1
    endloop
  endfacet
endsolid test
"""
    stl_path.write_text(content)
    return stl_path


@pytest.fixture
def truncated_stl(temp_dir):
    """Create a truncated/corrupted STL file"""
    stl_path = temp_dir / "truncated.stl"

    with open(stl_path, 'wb') as f:
        # Write header
        f.write(b"binary STL".ljust(80, b'\x00'))
        # Write triangle count claiming 100 triangles
        f.write(struct.pack('<I', 100))
        # But only write data for 1 triangle
        f.write(struct.pack('<3f', 0.0, 0.0, 0.0))  # normal
        f.write(struct.pack('<3f', 0.0, 0.0, 0.0))  # v1
        f.write(struct.pack('<3f', 1.0, 0.0, 0.0))  # v2
        f.write(struct.pack('<3f', 0.0, 1.0, 0.0))  # v3
        f.write(struct.pack('<H', 0))  # attribute

    return stl_path


@pytest.fixture
def empty_file(temp_dir):
    """Create an empty file"""
    stl_path = temp_dir / "empty.stl"
    stl_path.touch()
    return stl_path


@pytest.fixture
def fixed_wheel_stl(wheel_stl_path, temp_dir):
    """Create a fixed version of the wheel STL for testing"""
    from stl_validator import fix_binary_stl_header

    if not wheel_stl_path.exists():
        pytest.skip("Wheel STL fixture not available")

    fixed_path = temp_dir / "wheel_fixed.stl"
    shutil.copy(wheel_stl_path, fixed_path)
    fix_binary_stl_header(fixed_path, backup=False)
    return fixed_path


@pytest.fixture
def millimeter_stl(temp_dir):
    """Create a binary STL with millimeter-scale geometry (like a wheel)"""
    stl_path = temp_dir / "wheel_mm.stl"

    # Create a simple circle-ish shape at ~600mm diameter
    import math
    n_segments = 8
    radius = 300.0  # mm
    thickness = 20.0  # mm

    triangles = []

    # Create triangular facets around the rim
    for i in range(n_segments):
        angle1 = 2 * math.pi * i / n_segments
        angle2 = 2 * math.pi * (i + 1) / n_segments

        x1, y1 = radius * math.cos(angle1), radius * math.sin(angle1)
        x2, y2 = radius * math.cos(angle2), radius * math.sin(angle2)

        # Front face triangle
        triangles.append([
            (0.0, 0.0, 0.0),
            (x1, y1, 0.0),
            (x2, y2, 0.0)
        ])
        # Back face triangle
        triangles.append([
            (0.0, 0.0, thickness),
            (x2, y2, thickness),
            (x1, y1, thickness)
        ])

    with open(stl_path, 'wb') as f:
        header = b"binary STL - wheel in millimeters"
        f.write(header.ljust(80, b'\x00'))
        f.write(struct.pack('<I', len(triangles)))

        for tri in triangles:
            f.write(struct.pack('<3f', 0.0, 0.0, 0.0))  # normal
            for vertex in tri:
                f.write(struct.pack('<3f', *vertex))
            f.write(struct.pack('<H', 0))

    return stl_path
