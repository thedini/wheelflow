"""
WheelFlow Visualization Module
Generates visualizations for CFD results including:
- Force coefficient charts
- Pressure slices
- 3D pressure surfaces
- Hero images (ParaView)
"""

from .force_distribution import (
    extract_force_distribution,
    extract_convergence_history,
    calculate_forces,
    extract_yaw_series
)
from .pressure_slices import generate_pressure_slices
from .results_summary import generate_results_summary
from .hero_image import generate_hero_image, check_paraview_available
from .pressure_surface import (
    export_pressure_surface_ply,
    export_pressure_surface_json
)

__all__ = [
    'extract_force_distribution',
    'extract_convergence_history',
    'calculate_forces',
    'extract_yaw_series',
    'generate_pressure_slices',
    'generate_results_summary',
    'generate_hero_image',
    'check_paraview_available',
    'export_pressure_surface_ply',
    'export_pressure_surface_json',
]
