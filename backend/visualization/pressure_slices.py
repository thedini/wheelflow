"""
Pressure Slice Visualization
Generates 2D pressure/velocity slices through the flow domain
"""

from pathlib import Path
from typing import Dict, List, Optional
import subprocess
import json


def generate_slice_function_object(positions: List[float] = None) -> str:
    """
    Generate OpenFOAM function object for pressure slices.

    Args:
        positions: list of x-positions for slices (default: around wheel)

    Returns:
        String content for controlDict functions section
    """
    if positions is None:
        positions = [-0.3, -0.1, 0.0, 0.1, 0.3, 0.5, 1.0, 2.0]

    slices = []
    for i, x in enumerate(positions):
        slices.append(f"""
            slice_x{i}
            {{
                type        cuttingPlane;
                planeType   pointAndNormal;
                pointAndNormalDict
                {{
                    point   ({x} 0 0.35);
                    normal  (1 0 0);
                }}
                interpolate true;
            }}""")

    function_object = f"""
    pressureSlices
    {{
        type            surfaces;
        libs            (sampling);
        writeControl    writeTime;
        surfaceFormat   raw;
        fields          (p U);

        surfaces
        {{
            {''.join(slices)}
        }}
    }}
"""
    return function_object


def generate_pressure_slices(case_dir: Path, output_dir: Path = None) -> Dict:
    """
    Extract pressure slice data from OpenFOAM postProcessing.

    Returns dict with slice data for each position.
    """
    if output_dir is None:
        output_dir = case_dir / "visualizations" / "slices"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "slices": [],
        "colormap": {"min": -0.6, "max": 1.0, "name": "viridis"}
    }

    # Look for sampling output
    sampling_dir = case_dir / "postProcessing" / "pressureSlices"

    if not sampling_dir.exists():
        # Try alternative paths
        for alt_name in ["surfaces", "cuttingPlane", "slices"]:
            alt_dir = case_dir / "postProcessing" / alt_name
            if alt_dir.exists():
                sampling_dir = alt_dir
                break

    if not sampling_dir.exists():
        result["error"] = "No slice data found. Add pressureSlices function object to controlDict."
        return result

    # Find latest time directory
    time_dirs = sorted([d for d in sampling_dir.iterdir() if d.is_dir()],
                       key=lambda x: float(x.name) if x.name.replace('.', '').isdigit() else 0)

    if not time_dirs:
        result["error"] = "No time directories found in postProcessing"
        return result

    latest_time = time_dirs[-1]

    # Parse raw slice data
    for slice_file in latest_time.glob("*.raw"):
        slice_data = parse_raw_slice(slice_file)
        if slice_data:
            result["slices"].append(slice_data)

    return result


def parse_raw_slice(file_path: Path) -> Optional[Dict]:
    """
    Parse OpenFOAM raw surface format.

    Raw format: x y z value (one point per line)
    """
    try:
        points = []
        values = []

        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split()
                if len(parts) >= 4:
                    x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
                    value = float(parts[3])
                    points.append([x, y, z])
                    values.append(value)

        if not points:
            return None

        # Extract slice position from filename
        name = file_path.stem
        x_pos = 0.0
        if 'x' in name:
            try:
                x_pos = float(name.split('x')[-1].replace('_p', '').replace('_U', ''))
            except ValueError:
                pass

        return {
            "name": name,
            "x_position": x_pos,
            "points": points,
            "values": values,
            "bounds": {
                "y_min": min(p[1] for p in points),
                "y_max": max(p[1] for p in points),
                "z_min": min(p[2] for p in points),
                "z_max": max(p[2] for p in points),
            },
            "value_range": {
                "min": min(values),
                "max": max(values)
            }
        }

    except Exception as e:
        return None


def calculate_pressure_coefficient(p_kinematic: float, U_inf: float = 13.9, rho: float = 1.225) -> float:
    """
    Convert kinematic pressure to pressure coefficient.

    Cp = (p - p_inf) / (0.5 * rho * U^2)

    For kinematic pressure (p/rho): Cp = p_kinematic / (0.5 * U^2)
    """
    q = 0.5 * U_inf * U_inf  # Dynamic pressure (kinematic)
    return p_kinematic / q


def slice_to_image_data(slice_data: Dict, resolution: int = 100) -> Dict:
    """
    Convert slice point data to regular grid for image rendering.

    Returns dict with:
    - width, height
    - data: 2D array of pressure values
    - extent: [y_min, y_max, z_min, z_max]
    """
    if not slice_data or not slice_data.get("points"):
        return None

    from scipy.interpolate import griddata
    import numpy as np

    points = np.array(slice_data["points"])
    values = np.array(slice_data["values"])

    # Extract y, z coordinates (slice is perpendicular to x)
    y = points[:, 1]
    z = points[:, 2]

    # Create regular grid
    bounds = slice_data["bounds"]
    yi = np.linspace(bounds["y_min"], bounds["y_max"], resolution)
    zi = np.linspace(bounds["z_min"], bounds["z_max"], resolution)
    yi_grid, zi_grid = np.meshgrid(yi, zi)

    # Interpolate to grid
    grid_values = griddata((y, z), values, (yi_grid, zi_grid), method='linear')

    return {
        "width": resolution,
        "height": resolution,
        "data": grid_values.tolist() if grid_values is not None else None,
        "extent": [bounds["y_min"], bounds["y_max"], bounds["z_min"], bounds["z_max"]]
    }
