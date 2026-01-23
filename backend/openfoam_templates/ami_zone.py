"""
AMI (Arbitrary Mesh Interface) Zone Generation for Rotating Wheel

Creates the rotating zone geometry and configuration for wheel rotation
simulation using AMI interfaces.
"""

import math
import struct
from pathlib import Path
from typing import Tuple


def generate_ami_cylinder_stl(output_path: Path,
                               center: Tuple[float, float, float],
                               radius: float,
                               height: float,
                               axis: str = 'y',
                               num_segments: int = 64) -> dict:
    """
    Generate an STL cylinder for the AMI rotating zone.

    The cylinder should be slightly larger than the wheel to enclose it
    while leaving clearance for the ground.

    Args:
        output_path: Path to write STL file
        center: Center point (x, y, z) of the cylinder
        radius: Radius of the cylinder (should be > wheel radius)
        height: Height/length of the cylinder along axis
        axis: Rotation axis ('x', 'y', or 'z')
        num_segments: Number of segments for cylinder approximation

    Returns:
        dict with cylinder info
    """
    triangles = []

    # Generate cylinder mesh
    for i in range(num_segments):
        theta1 = 2 * math.pi * i / num_segments
        theta2 = 2 * math.pi * (i + 1) / num_segments

        cos1, sin1 = math.cos(theta1), math.sin(theta1)
        cos2, sin2 = math.cos(theta2), math.sin(theta2)

        if axis == 'y':
            # Cylinder along Y axis (wheel axle direction)
            # Bottom points (y = center[1] - height/2)
            b1 = (center[0] + radius * cos1, center[1] - height / 2, center[2] + radius * sin1)
            b2 = (center[0] + radius * cos2, center[1] - height / 2, center[2] + radius * sin2)
            # Top points (y = center[1] + height/2)
            t1 = (center[0] + radius * cos1, center[1] + height / 2, center[2] + radius * sin1)
            t2 = (center[0] + radius * cos2, center[1] + height / 2, center[2] + radius * sin2)
        elif axis == 'x':
            # Cylinder along X axis
            b1 = (center[0] - height / 2, center[1] + radius * cos1, center[2] + radius * sin1)
            b2 = (center[0] - height / 2, center[1] + radius * cos2, center[2] + radius * sin2)
            t1 = (center[0] + height / 2, center[1] + radius * cos1, center[2] + radius * sin1)
            t2 = (center[0] + height / 2, center[1] + radius * cos2, center[2] + radius * sin2)
        else:  # z
            # Cylinder along Z axis
            b1 = (center[0] + radius * cos1, center[1] + radius * sin1, center[2] - height / 2)
            b2 = (center[0] + radius * cos2, center[1] + radius * sin2, center[2] - height / 2)
            t1 = (center[0] + radius * cos1, center[1] + radius * sin1, center[2] + height / 2)
            t2 = (center[0] + radius * cos2, center[1] + radius * sin2, center[2] + height / 2)

        # Side triangles (2 per segment)
        triangles.append((b1, b2, t1))
        triangles.append((t1, b2, t2))

        # Bottom cap triangles
        if axis == 'y':
            bc = (center[0], center[1] - height / 2, center[2])
            tc = (center[0], center[1] + height / 2, center[2])
        elif axis == 'x':
            bc = (center[0] - height / 2, center[1], center[2])
            tc = (center[0] + height / 2, center[1], center[2])
        else:
            bc = (center[0], center[1], center[2] - height / 2)
            tc = (center[0], center[1], center[2] + height / 2)

        triangles.append((bc, b2, b1))  # Bottom cap
        triangles.append((tc, t1, t2))  # Top cap

    # Write binary STL
    with open(output_path, 'wb') as f:
        # Header (80 bytes)
        header = b'AMI rotating zone cylinder - WheelFlow' + b'\0' * 42
        f.write(header[:80])

        # Number of triangles
        f.write(struct.pack('<I', len(triangles)))

        # Write triangles
        for v1, v2, v3 in triangles:
            # Calculate normal
            ax, ay, az = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
            bx, by, bz = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
            nx = ay * bz - az * by
            ny = az * bx - ax * bz
            nz = ax * by - ay * bx
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            if length > 0:
                nx, ny, nz = nx / length, ny / length, nz / length

            # Normal
            f.write(struct.pack('<fff', nx, ny, nz))
            # Vertices
            f.write(struct.pack('<fff', *v1))
            f.write(struct.pack('<fff', *v2))
            f.write(struct.pack('<fff', *v3))
            # Attribute byte count
            f.write(struct.pack('<H', 0))

    return {
        'path': str(output_path),
        'center': center,
        'radius': radius,
        'height': height,
        'axis': axis,
        'num_triangles': len(triangles)
    }


def generate_ami_zone_dict(wheel_center: Tuple[float, float, float],
                            wheel_radius: float,
                            wheel_width: float,
                            clearance_factor: float = 1.15) -> str:
    """
    Generate snappyHexMeshDict geometry section for AMI zone.

    The AMI zone is a cylinder enclosing the wheel with some clearance.
    The bottom is cut off at ground level (z=0) to avoid intersection.

    Args:
        wheel_center: Center of the wheel (x, y, z)
        wheel_radius: Wheel radius in meters
        wheel_width: Wheel width in meters
        clearance_factor: Factor to enlarge AMI zone beyond wheel bounds

    Returns:
        String containing the geometry section for snappyHexMeshDict
    """
    # AMI cylinder parameters
    ami_radius = wheel_radius * clearance_factor
    ami_width = wheel_width * clearance_factor

    # Center the AMI zone on the wheel
    # Note: wheel center z is at wheel_radius (sitting on ground)
    cx, cy, cz = wheel_center

    geometry_section = f'''
    // AMI rotating zone - encloses wheel for rotation simulation
    AMI_zone
    {{
        type    searchableCylinder;
        point1  ({cx} {cy - ami_width/2} {cz});
        point2  ({cx} {cy + ami_width/2} {cz});
        radius  {ami_radius};
    }}
'''

    return geometry_section


def generate_cell_zone_dict(case_dir: Path, zone_name: str = "rotatingZone") -> str:
    """
    Generate topoSetDict for creating cell zone for AMI rotation.
    """
    topo_set_dict = f'''FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      topoSetDict;
}}

actions
(
    {{
        name    {zone_name};
        type    cellSet;
        action  new;
        source  cylinderToCell;
        sourceInfo
        {{
            type cylinder;
            p1 (0 -0.1 0.35);  // Adjust based on wheel position
            p2 (0 0.1 0.35);
            radius 0.4;  // Adjust based on wheel radius
        }}
    }}
    {{
        name    {zone_name};
        type    cellZoneSet;
        action  new;
        source  setToCellZone;
        sourceInfo
        {{
            set {zone_name};
        }}
    }}
);
'''
    return topo_set_dict
