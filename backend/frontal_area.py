"""
Frontal Area Calculation Module for WheelFlow

Calculates the projected frontal area of STL geometry for accurate
aerodynamic coefficient calculation. This is critical for matching
AeroCloud's reference area methodology.

AeroCloud uses Aref = 0.0225 m² for bicycle wheels.
"""

import struct
from pathlib import Path
from typing import Tuple, List, Optional
import math


def parse_binary_stl(file_path: Path) -> List[Tuple[Tuple[float, float, float], ...]]:
    """
    Parse binary STL file and return list of triangles.
    Each triangle is a tuple of 3 vertices (x, y, z).
    """
    triangles = []

    with open(file_path, 'rb') as f:
        # Skip 80-byte header
        f.read(80)

        # Read number of triangles
        num_triangles = struct.unpack('<I', f.read(4))[0]

        for _ in range(num_triangles):
            # Skip normal (12 bytes)
            f.read(12)

            # Read 3 vertices
            vertices = []
            for _ in range(3):
                x, y, z = struct.unpack('<fff', f.read(12))
                vertices.append((x, y, z))

            triangles.append(tuple(vertices))

            # Skip attribute byte count
            f.read(2)

    return triangles


def project_triangle_area(v1: Tuple[float, float, float],
                          v2: Tuple[float, float, float],
                          v3: Tuple[float, float, float],
                          direction: str = 'x') -> float:
    """
    Calculate the projected area of a triangle onto a plane perpendicular to direction.

    Args:
        v1, v2, v3: Triangle vertices (x, y, z)
        direction: Flow direction - 'x', 'y', or 'z'

    Returns:
        Projected area (always positive)
    """
    # Select coordinates for projection based on direction
    if direction == 'x':
        # Project onto YZ plane
        a = (v1[1], v1[2])
        b = (v2[1], v2[2])
        c = (v3[1], v3[2])
    elif direction == 'y':
        # Project onto XZ plane
        a = (v1[0], v1[2])
        b = (v2[0], v2[2])
        c = (v3[0], v3[2])
    else:  # z
        # Project onto XY plane
        a = (v1[0], v1[1])
        b = (v2[0], v2[1])
        c = (v3[0], v3[1])

    # Calculate 2D triangle area using cross product
    # Area = 0.5 * |AB x AC|
    ab = (b[0] - a[0], b[1] - a[1])
    ac = (c[0] - a[0], c[1] - a[1])

    cross = ab[0] * ac[1] - ab[1] * ac[0]
    return abs(cross) / 2.0


def calculate_frontal_area_simple(stl_path: Path, direction: str = 'x') -> dict:
    """
    Calculate frontal area using simple projection method.

    This sums the projected areas of all triangles, which can overestimate
    for complex geometry with overlapping projections.

    Args:
        stl_path: Path to STL file
        direction: Flow direction ('x' for standard setup)

    Returns:
        dict with area and metadata
    """
    triangles = parse_binary_stl(stl_path)

    total_area = 0.0
    min_coords = [float('inf'), float('inf'), float('inf')]
    max_coords = [float('-inf'), float('-inf'), float('-inf')]

    for v1, v2, v3 in triangles:
        total_area += project_triangle_area(v1, v2, v3, direction)

        for v in [v1, v2, v3]:
            for i in range(3):
                min_coords[i] = min(min_coords[i], v[i])
                max_coords[i] = max(max_coords[i], v[i])

    # For a wheel, the theoretical frontal area is approximately:
    # A = diameter * width (rectangular approximation)
    # or A = pi * r^2 for circular projection

    dimensions = [max_coords[i] - min_coords[i] for i in range(3)]

    if direction == 'x':
        # YZ plane - height (z) and width (y)
        bounding_box_area = dimensions[1] * dimensions[2]
    elif direction == 'y':
        bounding_box_area = dimensions[0] * dimensions[2]
    else:
        bounding_box_area = dimensions[0] * dimensions[1]

    return {
        'projected_area': total_area,
        'bounding_box_area': bounding_box_area,
        'dimensions': dimensions,
        'min_coords': min_coords,
        'max_coords': max_coords,
        'num_triangles': len(triangles),
        'direction': direction
    }


def calculate_frontal_area_rasterized(stl_path: Path,
                                       direction: str = 'x',
                                       resolution: int = 500) -> dict:
    """
    Calculate frontal area using rasterization method.

    This projects all triangles onto a 2D grid and counts occupied cells,
    properly handling overlapping geometry.

    Args:
        stl_path: Path to STL file
        direction: Flow direction
        resolution: Grid resolution (higher = more accurate)

    Returns:
        dict with area and metadata
    """
    triangles = parse_binary_stl(stl_path)

    if not triangles:
        return {'frontal_area': 0.0, 'error': 'No triangles found'}

    # Find bounding box
    min_coords = [float('inf'), float('inf'), float('inf')]
    max_coords = [float('-inf'), float('-inf'), float('-inf')]

    for v1, v2, v3 in triangles:
        for v in [v1, v2, v3]:
            for i in range(3):
                min_coords[i] = min(min_coords[i], v[i])
                max_coords[i] = max(max_coords[i], v[i])

    # Select projection plane based on direction
    if direction == 'x':
        idx1, idx2 = 1, 2  # Y, Z
    elif direction == 'y':
        idx1, idx2 = 0, 2  # X, Z
    else:
        idx1, idx2 = 0, 1  # X, Y

    # Create rasterization grid
    range1 = max_coords[idx1] - min_coords[idx1]
    range2 = max_coords[idx2] - min_coords[idx2]

    if range1 == 0 or range2 == 0:
        return {'frontal_area': 0.0, 'error': 'Zero-dimension geometry'}

    # Adjust resolution to maintain aspect ratio
    if range1 > range2:
        res1 = resolution
        res2 = max(1, int(resolution * range2 / range1))
    else:
        res2 = resolution
        res1 = max(1, int(resolution * range1 / range2))

    cell_size1 = range1 / res1
    cell_size2 = range2 / res2
    cell_area = cell_size1 * cell_size2

    # Initialize occupancy grid
    grid = [[False] * res2 for _ in range(res1)]

    def point_in_triangle_2d(px, py, ax, ay, bx, by, cx, cy):
        """Check if point (px, py) is inside triangle ABC using barycentric coords"""
        v0x, v0y = cx - ax, cy - ay
        v1x, v1y = bx - ax, by - ay
        v2x, v2y = px - ax, py - ay

        dot00 = v0x * v0x + v0y * v0y
        dot01 = v0x * v1x + v0y * v1y
        dot02 = v0x * v2x + v0y * v2y
        dot11 = v1x * v1x + v1y * v1y
        dot12 = v1x * v2x + v1y * v2y

        denom = dot00 * dot11 - dot01 * dot01
        if abs(denom) < 1e-12:
            return False

        inv_denom = 1.0 / denom
        u = (dot11 * dot02 - dot01 * dot12) * inv_denom
        v = (dot00 * dot12 - dot01 * dot02) * inv_denom

        return (u >= 0) and (v >= 0) and (u + v <= 1)

    # Rasterize each triangle
    for v1, v2, v3 in triangles:
        # Project vertices
        a = (v1[idx1], v1[idx2])
        b = (v2[idx1], v2[idx2])
        c = (v3[idx1], v3[idx2])

        # Find triangle bounding box in grid coordinates
        min_i = max(0, int((min(a[0], b[0], c[0]) - min_coords[idx1]) / cell_size1))
        max_i = min(res1 - 1, int((max(a[0], b[0], c[0]) - min_coords[idx1]) / cell_size1))
        min_j = max(0, int((min(a[1], b[1], c[1]) - min_coords[idx2]) / cell_size2))
        max_j = min(res2 - 1, int((max(a[1], b[1], c[1]) - min_coords[idx2]) / cell_size2))

        # Check each cell in bounding box
        for i in range(min_i, max_i + 1):
            for j in range(min_j, max_j + 1):
                if not grid[i][j]:
                    # Cell center
                    px = min_coords[idx1] + (i + 0.5) * cell_size1
                    py = min_coords[idx2] + (j + 0.5) * cell_size2

                    if point_in_triangle_2d(px, py, a[0], a[1], b[0], b[1], c[0], c[1]):
                        grid[i][j] = True

    # Count occupied cells
    occupied_cells = sum(sum(row) for row in grid)
    frontal_area = occupied_cells * cell_area

    dimensions = [max_coords[i] - min_coords[i] for i in range(3)]
    bounding_area = range1 * range2

    return {
        'frontal_area': frontal_area,
        'bounding_box_area': bounding_area,
        'solidity': frontal_area / bounding_area if bounding_area > 0 else 0,
        'dimensions': dimensions,
        'min_coords': min_coords,
        'max_coords': max_coords,
        'num_triangles': len(triangles),
        'grid_resolution': (res1, res2),
        'cell_area': cell_area,
        'occupied_cells': occupied_cells,
        'direction': direction
    }


def calculate_wheel_frontal_area(stl_path: Path,
                                  wheel_diameter: Optional[float] = None,
                                  wheel_width: Optional[float] = None) -> dict:
    """
    Calculate frontal area specifically for bicycle wheel geometry.

    Uses rasterized method for accuracy and provides comparison with
    theoretical values.

    Args:
        stl_path: Path to transformed STL file (in meters, oriented correctly)
        wheel_diameter: Known wheel diameter (m), or None to detect
        wheel_width: Known wheel width (m), or None to detect

    Returns:
        dict with frontal_area, method comparison, and recommendations
    """
    # Get accurate rasterized area
    raster_result = calculate_frontal_area_rasterized(stl_path, direction='x', resolution=500)

    if 'error' in raster_result:
        return raster_result

    dims = raster_result['dimensions']

    # For a wheel oriented with X as flow direction:
    # - X is the flow direction (axle direction is Y)
    # - Y is the wheel width
    # - Z is the wheel height
    detected_width = dims[1]  # Y dimension
    detected_diameter = dims[2]  # Z dimension

    if wheel_diameter is None:
        wheel_diameter = detected_diameter
    if wheel_width is None:
        wheel_width = detected_width

    # Calculate theoretical areas for comparison
    # 1. Circular projection (if wheel were solid disk)
    circular_area = math.pi * (wheel_diameter / 2) ** 2

    # 2. Rectangular approximation
    rectangular_area = wheel_diameter * wheel_width

    # 3. AeroCloud reference area (standard for bicycle wheels)
    aerocloud_aref = 0.0225  # m²

    # The actual frontal area from rasterization
    actual_area = raster_result['frontal_area']

    # Solidity = actual / bounding box
    # For a typical spoked wheel, this is usually 0.3-0.5
    solidity = raster_result['solidity']

    return {
        'frontal_area': actual_area,
        'frontal_area_cm2': actual_area * 10000,  # Convert to cm²
        'wheel_diameter': wheel_diameter,
        'wheel_width': wheel_width,
        'detected_diameter': detected_diameter,
        'detected_width': detected_width,
        'solidity': solidity,
        'comparison': {
            'aerocloud_aref': aerocloud_aref,
            'circular_area': circular_area,
            'rectangular_area': rectangular_area,
            'ratio_to_aerocloud': actual_area / aerocloud_aref if aerocloud_aref > 0 else 0,
        },
        'recommendations': {
            'use_calculated': actual_area,
            'use_aerocloud_standard': aerocloud_aref,
            'note': 'AeroCloud uses fixed Aref=0.0225 m² for bicycle wheels'
        },
        'rasterization': {
            'resolution': raster_result['grid_resolution'],
            'occupied_cells': raster_result['occupied_cells'],
        }
    }


def get_frontal_area_for_simulation(stl_path: Path,
                                     use_aerocloud_standard: bool = True) -> Tuple[float, dict]:
    """
    Get the frontal area to use for CFD simulation.

    Args:
        stl_path: Path to transformed STL file
        use_aerocloud_standard: If True, use AeroCloud's standard Aref (for comparison)
                                If False, use calculated actual area

    Returns:
        Tuple of (Aref value to use, full analysis dict)
    """
    analysis = calculate_wheel_frontal_area(stl_path)

    if 'error' in analysis:
        # Fall back to AeroCloud standard
        return 0.0225, {'error': analysis['error'], 'fallback': True}

    if use_aerocloud_standard:
        # Use AeroCloud's reference for direct comparison
        aref = 0.0225
    else:
        # Use calculated area
        aref = analysis['frontal_area']

    analysis['aref_used'] = aref
    analysis['aref_method'] = 'aerocloud_standard' if use_aerocloud_standard else 'calculated'

    return aref, analysis


if __name__ == "__main__":
    # Test with a sample STL file
    import sys

    if len(sys.argv) > 1:
        stl_file = Path(sys.argv[1])
        if stl_file.exists():
            print(f"Analyzing: {stl_file}")
            result = calculate_wheel_frontal_area(stl_file)

            print(f"\n=== Frontal Area Analysis ===")
            print(f"Frontal Area: {result['frontal_area']:.6f} m² ({result['frontal_area_cm2']:.2f} cm²)")
            print(f"Wheel Diameter: {result['wheel_diameter']:.3f} m")
            print(f"Wheel Width: {result['wheel_width']:.3f} m")
            print(f"Solidity: {result['solidity']:.2%}")
            print(f"\nComparison:")
            print(f"  AeroCloud Aref: {result['comparison']['aerocloud_aref']:.4f} m²")
            print(f"  Ratio to AeroCloud: {result['comparison']['ratio_to_aerocloud']:.2f}x")
        else:
            print(f"File not found: {stl_file}")
    else:
        print("Usage: python frontal_area.py <stl_file>")
