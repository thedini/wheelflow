"""
Dynamic Mesh Configuration for Rotating Wheel

Generates dynamicMeshDict for solid body rotation using MRF (Moving Reference Frame)
or AMI (Arbitrary Mesh Interface) approaches.

MRF Approach:
- Simpler to implement
- Works with steady-state solvers
- Adds source terms to momentum equation
- Good for isolated rotating regions

AMI Approach:
- More accurate for complex geometries
- Requires transient solver (pimpleFoam)
- Mesh actually rotates
- Better for wheel-ground interaction
"""

from pathlib import Path
from typing import Tuple
import math


def generate_mrf_properties(zone_name: str,
                             origin: Tuple[float, float, float],
                             axis: Tuple[float, float, float],
                             omega: float,
                             non_rotating_patches: list = None) -> str:
    """
    Generate MRFProperties dict for Moving Reference Frame approach.

    This is the simpler approach that works with steady-state solvers.
    The mesh doesn't actually rotate - instead, source terms are added
    to the momentum equation to simulate rotation effects.

    Args:
        zone_name: Name of the cell zone to rotate
        origin: Rotation origin (x, y, z)
        axis: Rotation axis (usually (0, 1, 0) for Y-axis)
        omega: Angular velocity in rad/s
        non_rotating_patches: Patches that should not rotate (e.g., wheel surface)

    Returns:
        MRFProperties dictionary content
    """
    if non_rotating_patches is None:
        non_rotating_patches = []

    patches_str = '\n            '.join(non_rotating_patches) if non_rotating_patches else ''

    mrf_properties = f'''FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      MRFProperties;
}}

// Moving Reference Frame for wheel rotation
// Adds Coriolis and centrifugal forces to momentum equation

MRF1
{{
    cellZone    {zone_name};
    active      yes;

    // Non-rotating patches (walls that move with the fluid, not the frame)
    nonRotatingPatches
    (
        {patches_str}
    );

    origin      ({origin[0]} {origin[1]} {origin[2]});
    axis        ({axis[0]} {axis[1]} {axis[2]});
    omega       {omega};  // rad/s = V/R
}}
'''
    return mrf_properties


def generate_dynamic_mesh_dict(zone_name: str,
                                origin: Tuple[float, float, float],
                                axis: Tuple[float, float, float],
                                omega: float,
                                use_ami: bool = False) -> str:
    """
    Generate dynamicMeshDict for mesh rotation.

    Args:
        zone_name: Name of the cell zone to rotate
        origin: Rotation origin (x, y, z)
        axis: Rotation axis
        omega: Angular velocity in rad/s
        use_ami: If True, use full dynamic mesh (AMI)
                 If False, use MRF approach

    Returns:
        dynamicMeshDict content
    """
    if use_ami:
        # Full AMI dynamic mesh - mesh actually rotates
        dynamic_mesh_dict = f'''FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      dynamicMeshDict;
}}

// Dynamic mesh with solid body rotation for wheel
// Requires transient solver (pimpleFoam)

dynamicFvMesh   dynamicMotionSolverFvMesh;

motionSolverLibs ("libfvMotionSolvers.so");

motionSolver    solidBody;

cellZone        {zone_name};

solidBodyMotionFunction rotatingMotion;

rotatingMotionCoeffs
{{
    origin      ({origin[0]} {origin[1]} {origin[2]});
    axis        ({axis[0]} {axis[1]} {axis[2]});
    omega       constant {omega};  // rad/s
}}
'''
    else:
        # Static mesh - use MRF instead
        dynamic_mesh_dict = f'''FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      dynamicMeshDict;
}}

// Static mesh - rotation handled by MRF (see MRFProperties)
dynamicFvMesh   staticFvMesh;
'''

    return dynamic_mesh_dict


def generate_fv_options_mrf(zone_name: str,
                             origin: Tuple[float, float, float],
                             axis: Tuple[float, float, float],
                             omega: float) -> str:
    """
    Generate fvOptions dict with MRF source.

    Alternative to MRFProperties - uses fvOptions framework.
    This is the recommended approach in newer OpenFOAM versions.

    Args:
        zone_name: Name of the cell zone
        origin: Rotation origin
        axis: Rotation axis
        omega: Angular velocity in rad/s

    Returns:
        fvOptions dictionary content
    """
    fv_options = f'''FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvOptions;
}}

// MRF zone for wheel rotation
MRF1
{{
    type            MRFSource;
    active          yes;

    MRFSourceCoeffs
    {{
        cellZone    {zone_name};
        origin      ({origin[0]} {origin[1]} {origin[2]});
        axis        ({axis[0]} {axis[1]} {axis[2]});
        omega       {omega};
    }}
}}
'''
    return fv_options


def calculate_rotation_params(speed: float, wheel_radius: float) -> dict:
    """
    Calculate rotation parameters from linear speed and wheel radius.

    For a rolling wheel without slip:
    - Linear velocity at contact point = ground velocity
    - Angular velocity = V / R

    Args:
        speed: Ground speed (m/s)
        wheel_radius: Wheel radius (m)

    Returns:
        dict with omega, rpm, period, tip_speed
    """
    omega = speed / wheel_radius  # rad/s
    rpm = omega * 60 / (2 * math.pi)  # revolutions per minute
    period = 2 * math.pi / omega if omega > 0 else float('inf')  # seconds per revolution
    tip_speed = omega * wheel_radius  # Should equal input speed for no-slip

    return {
        'omega': omega,
        'rpm': rpm,
        'period': period,
        'tip_speed': tip_speed,
        'linear_speed': speed,
        'radius': wheel_radius
    }


def generate_create_patch_dict_ami() -> str:
    """
    Generate createPatchDict for creating AMI interface patches.

    After snappyHexMesh creates the mesh with the AMI zone geometry,
    createPatch is used to convert the interface faces to cyclicAMI type.
    """
    create_patch_dict = '''FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      createPatchDict;
}

// Create AMI (Arbitrary Mesh Interface) patches for rotating zone

pointSync false;

patches
(
    {
        // Inner side of AMI (rotates with wheel)
        name AMI_inner;
        patchInfo
        {
            type cyclicAMI;
            matchTolerance 0.0001;
            neighbourPatch AMI_outer;
            transform noOrdering;
        }
        constructFrom patches;
        patches (AMI_zone);  // From snappyHexMesh
    }

    {
        // Outer side of AMI (stationary)
        name AMI_outer;
        patchInfo
        {
            type cyclicAMI;
            matchTolerance 0.0001;
            neighbourPatch AMI_inner;
            transform noOrdering;
        }
        constructFrom patches;
        patches (AMI_zone_slave);  // Will need adjustment
    }
);
'''
    return create_patch_dict
