"""
OpenFOAM Templates Module for WheelFlow

Provides template generators for:
- AMI (Arbitrary Mesh Interface) rotating zones
- Dynamic mesh configuration
- Transient solver settings (pimpleFoam)
"""

from .dynamic_mesh import generate_dynamic_mesh_dict
from .ami_zone import generate_ami_cylinder_stl, generate_ami_zone_dict
from .pimple_settings import generate_pimple_fv_solution, generate_transient_control_dict
from .boundary_conditions import generate_rotating_wheel_bc

__all__ = [
    'generate_dynamic_mesh_dict',
    'generate_ami_cylinder_stl',
    'generate_ami_zone_dict',
    'generate_pimple_fv_solution',
    'generate_transient_control_dict',
    'generate_rotating_wheel_bc',
]
