"""
Boundary Conditions for Rotating Wheel Simulation

For a rotating wheel, the wheel surface velocity is NOT zero.
The velocity varies with position on the wheel surface based on:
- Rotation speed (omega)
- Distance from rotation axis
- Position relative to rotation axis

For proper rolling contact:
- At contact patch (bottom of wheel), surface velocity should match ground velocity
- At top of wheel, surface velocity is opposite to flow direction
"""

import math
from typing import Tuple


def generate_rotating_wheel_bc(speed: float,
                                 yaw: float,
                                 omega: float,
                                 wheel_center: Tuple[float, float, float],
                                 rotation_axis: Tuple[float, float, float] = (0, 1, 0)) -> str:
    """
    Generate velocity boundary condition for rotating wheel surface.

    Uses the rotatingWallVelocity boundary condition which calculates
    the local surface velocity based on rotation.

    Args:
        speed: Flow speed (m/s)
        yaw: Yaw angle (degrees)
        omega: Angular velocity (rad/s) - positive for forward roll
        wheel_center: Center of wheel rotation (x, y, z)
        rotation_axis: Axis of rotation (default Y for bicycle wheel)

    Returns:
        Wheel boundary condition block for U file
    """
    yaw_rad = math.radians(yaw)
    vx = speed * math.cos(yaw_rad)
    vy = speed * math.sin(yaw_rad)

    # For a forward-rolling wheel (moving in +X direction):
    # - Rotation is about Y axis
    # - Positive omega (counter-clockwise when viewed from +Y) makes bottom move +X
    # - This matches ground velocity for rolling without slip

    wheel_bc = f'''    wheel
    {{
        type            rotatingWallVelocity;
        origin          ({wheel_center[0]} {wheel_center[1]} {wheel_center[2]});
        axis            ({rotation_axis[0]} {rotation_axis[1]} {rotation_axis[2]});
        omega           {omega};  // rad/s (positive = forward roll)
    }}'''

    return wheel_bc


def generate_velocity_file_rotating(speed: float,
                                     yaw: float,
                                     omega: float,
                                     wheel_center: Tuple[float, float, float]) -> str:
    """
    Generate complete U (velocity) file with rotating wheel boundary condition.

    Args:
        speed: Flow speed (m/s)
        yaw: Yaw angle (degrees)
        omega: Angular velocity (rad/s)
        wheel_center: Center of wheel rotation (x, y, z)

    Returns:
        Complete U file content
    """
    yaw_rad = math.radians(yaw)
    vx = speed * math.cos(yaw_rad)
    vy = speed * math.sin(yaw_rad)

    u_file = f'''FoamFile
{{
    version     2.0;
    format      ascii;
    class       volVectorField;
    object      U;
}}

dimensions      [0 1 -1 0 0 0 0];

internalField   uniform ({vx} {vy} 0);

boundaryField
{{
    inlet
    {{
        type            fixedValue;
        value           uniform ({vx} {vy} 0);
    }}

    outlet
    {{
        type            inletOutlet;
        inletValue      uniform (0 0 0);
        value           $internalField;
    }}

    ground
    {{
        type            movingWallVelocity;
        value           uniform ({vx} {vy} 0);
    }}

    top
    {{
        type            slip;
    }}

    sides
    {{
        type            slip;
    }}

    wheel
    {{
        type            rotatingWallVelocity;
        origin          ({wheel_center[0]} {wheel_center[1]} {wheel_center[2]});
        axis            (0 1 0);  // Y-axis rotation
        omega           {omega};  // rad/s
    }}
}}
'''
    return u_file


def generate_all_field_files_rotating(speed: float,
                                       yaw: float,
                                       omega: float,
                                       wheel_center: Tuple[float, float, float],
                                       air_nu: float = 1.48e-5) -> dict:
    """
    Generate all field files (U, p, k, omega, nut) for rotating wheel simulation.

    Args:
        speed: Flow speed (m/s)
        yaw: Yaw angle (degrees)
        omega: Angular velocity (rad/s)
        wheel_center: Center of wheel rotation (x, y, z)
        air_nu: Kinematic viscosity (m²/s)

    Returns:
        dict with field name -> file content
    """
    fields = {}

    # Velocity field
    fields['U'] = generate_velocity_file_rotating(speed, yaw, omega, wheel_center)

    # Pressure field
    fields['p'] = '''FoamFile
{
    version     2.0;
    format      ascii;
    class       volScalarField;
    object      p;
}

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform 0;

boundaryField
{
    inlet
    {
        type            zeroGradient;
    }
    outlet
    {
        type            fixedValue;
        value           uniform 0;
    }
    ground
    {
        type            zeroGradient;
    }
    top
    {
        type            slip;
    }
    sides
    {
        type            slip;
    }
    wheel
    {
        type            zeroGradient;
    }
}
'''

    # Turbulent kinetic energy
    # Estimate inlet turbulence: I = 0.05 (5% intensity), k = 1.5 * (U * I)^2
    k_inlet = 1.5 * (speed * 0.05) ** 2
    fields['k'] = f'''FoamFile
{{
    version     2.0;
    format      ascii;
    class       volScalarField;
    object      k;
}}

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform {k_inlet:.6f};

boundaryField
{{
    inlet
    {{
        type            fixedValue;
        value           uniform {k_inlet:.6f};
    }}
    outlet
    {{
        type            inletOutlet;
        inletValue      uniform {k_inlet:.6f};
        value           $internalField;
    }}
    ground
    {{
        type            kqRWallFunction;
        value           uniform {k_inlet:.6f};
    }}
    top
    {{
        type            slip;
    }}
    sides
    {{
        type            slip;
    }}
    wheel
    {{
        type            kqRWallFunction;
        value           uniform {k_inlet:.6f};
    }}
}}
'''

    # Specific dissipation rate
    # omega = k^0.5 / (C_mu^0.25 * L), where L is turbulent length scale
    # For external flow, L ~ 0.07 * characteristic_length
    L_turb = 0.07 * 0.65  # 0.65m wheel diameter
    omega_inlet = k_inlet ** 0.5 / (0.09 ** 0.25 * L_turb)
    fields['omega'] = f'''FoamFile
{{
    version     2.0;
    format      ascii;
    class       volScalarField;
    object      omega;
}}

dimensions      [0 0 -1 0 0 0 0];

internalField   uniform {omega_inlet:.2f};

boundaryField
{{
    inlet
    {{
        type            fixedValue;
        value           uniform {omega_inlet:.2f};
    }}
    outlet
    {{
        type            inletOutlet;
        inletValue      uniform {omega_inlet:.2f};
        value           $internalField;
    }}
    ground
    {{
        type            omegaWallFunction;
        value           uniform {omega_inlet:.2f};
    }}
    top
    {{
        type            slip;
    }}
    sides
    {{
        type            slip;
    }}
    wheel
    {{
        type            omegaWallFunction;
        value           uniform {omega_inlet:.2f};
    }}
}}
'''

    # Turbulent viscosity
    fields['nut'] = '''FoamFile
{
    version     2.0;
    format      ascii;
    class       volScalarField;
    object      nut;
}

dimensions      [0 2 -1 0 0 0 0];

internalField   uniform 0;

boundaryField
{
    inlet
    {
        type            calculated;
        value           uniform 0;
    }
    outlet
    {
        type            calculated;
        value           uniform 0;
    }
    ground
    {
        type            nutkWallFunction;
        value           uniform 0;
    }
    top
    {
        type            calculated;
        value           uniform 0;
    }
    sides
    {
        type            calculated;
        value           uniform 0;
    }
    wheel
    {
        type            nutkWallFunction;
        value           uniform 0;
    }
}
'''

    return fields
