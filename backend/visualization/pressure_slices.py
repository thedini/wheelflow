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


def parse_vtk_file(vtk_path: Path) -> Optional[Dict]:
    """
    Parse VTK legacy format file to extract points and pressure values.

    Returns dict with points, values, and bounds.
    """
    try:
        with open(vtk_path, 'r') as f:
            content = f.read()

        # Parse VTK STRUCTURED_GRID or POLYDATA format
        lines = content.split('\n')
        points = []
        values = []
        reading_points = False
        reading_scalars = False
        n_points = 0

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if line.startswith('POINTS'):
                parts = line.split()
                n_points = int(parts[1])
                reading_points = True
                i += 1
                continue

            if reading_points and len(points) < n_points:
                # Parse point coordinates
                coords = line.split()
                for j in range(0, len(coords), 3):
                    if j + 2 < len(coords):
                        points.append([
                            float(coords[j]),
                            float(coords[j + 1]),
                            float(coords[j + 2])
                        ])
                i += 1
                continue

            if line.startswith('SCALARS') or line.startswith('POINT_DATA'):
                reading_points = False

            if line.startswith('SCALARS'):
                # Next line is LOOKUP_TABLE, then data
                i += 2  # Skip LOOKUP_TABLE line
                reading_scalars = True
                continue

            if reading_scalars:
                vals = line.split()
                for v in vals:
                    try:
                        values.append(float(v))
                    except ValueError:
                        pass

            i += 1

        if not points or not values:
            return None

        # Compute bounds
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        zs = [p[2] for p in points]

        return {
            "points": points,
            "values": values[:len(points)],  # Ensure same length
            "bounds": {
                "x_min": min(xs), "x_max": max(xs),
                "y_min": min(ys), "y_max": max(ys),
                "z_min": min(zs), "z_max": max(zs)
            },
            "value_range": {
                "min": min(values[:len(points)]) if values else 0,
                "max": max(values[:len(points)]) if values else 1
            }
        }

    except Exception as e:
        return {"error": str(e)}


def render_vtk_slice_image(vtk_path: Path, output_path: Path,
                            resolution: int = 400,
                            colormap: str = 'RdBu_r',
                            dark_theme: bool = True) -> Dict:
    """
    Render a VTK slice file to a PNG image using matplotlib.

    Args:
        vtk_path: Path to VTK file
        output_path: Path to save PNG image
        resolution: Grid resolution for interpolation
        colormap: Matplotlib colormap name
        dark_theme: Use dark background

    Returns:
        dict with status and image info
    """
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-GUI backend
        import matplotlib.pyplot as plt
        import numpy as np
        from scipy.interpolate import griddata

        # Parse VTK file
        data = parse_vtk_file(vtk_path)
        if not data or "error" in data:
            return {"success": False, "error": data.get("error", "Could not parse VTK file")}

        points = np.array(data["points"])
        values = np.array(data["values"])
        bounds = data["bounds"]

        # Determine slice orientation based on coordinate variance
        x_var = np.var(points[:, 0])
        y_var = np.var(points[:, 1])
        z_var = np.var(points[:, 2])

        min_var = min(x_var, y_var, z_var)
        if min_var == x_var:
            # YZ plane slice
            h_coord = points[:, 1]
            v_coord = points[:, 2]
            h_label, v_label = 'Y (m)', 'Z (m)'
            h_bounds = (bounds["y_min"], bounds["y_max"])
            v_bounds = (bounds["z_min"], bounds["z_max"])
        elif min_var == y_var:
            # XZ plane slice
            h_coord = points[:, 0]
            v_coord = points[:, 2]
            h_label, v_label = 'X (m)', 'Z (m)'
            h_bounds = (bounds["x_min"], bounds["x_max"])
            v_bounds = (bounds["z_min"], bounds["z_max"])
        else:
            # XY plane slice
            h_coord = points[:, 0]
            v_coord = points[:, 1]
            h_label, v_label = 'X (m)', 'Y (m)'
            h_bounds = (bounds["x_min"], bounds["x_max"])
            v_bounds = (bounds["y_min"], bounds["y_max"])

        # Create regular grid
        hi = np.linspace(h_bounds[0], h_bounds[1], resolution)
        vi = np.linspace(v_bounds[0], v_bounds[1], resolution)
        hi_grid, vi_grid = np.meshgrid(hi, vi)

        # Interpolate values to grid
        grid_values = griddata((h_coord, v_coord), values,
                               (hi_grid, vi_grid), method='linear')

        # Create figure with dark theme
        if dark_theme:
            plt.style.use('dark_background')
            fig_bg = '#0f1419'
            text_color = '#a0a0b0'
        else:
            fig_bg = 'white'
            text_color = 'black'

        fig, ax = plt.subplots(figsize=(8, 6), facecolor=fig_bg)
        ax.set_facecolor(fig_bg)

        # Plot pressure contour
        v_min, v_max = data["value_range"]["min"], data["value_range"]["max"]

        # Center colormap around zero if range spans zero
        if v_min < 0 < v_max:
            v_abs = max(abs(v_min), abs(v_max))
            v_min, v_max = -v_abs, v_abs

        im = ax.pcolormesh(hi_grid, vi_grid, grid_values,
                           cmap=colormap, vmin=v_min, vmax=v_max,
                           shading='auto')

        # Add colorbar
        cbar = plt.colorbar(im, ax=ax, label='Pressure (Pa)')
        cbar.ax.yaxis.label.set_color(text_color)
        cbar.ax.tick_params(colors=text_color)

        # Labels and title
        ax.set_xlabel(h_label, color=text_color)
        ax.set_ylabel(v_label, color=text_color)
        ax.tick_params(colors=text_color)
        ax.set_aspect('equal')

        # Determine title from file name
        slice_name = vtk_path.stem
        ax.set_title(f'Pressure Distribution - {slice_name}',
                     color=text_color, fontsize=12)

        # Save image
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, facecolor=fig_bg,
                    bbox_inches='tight', pad_inches=0.1)
        plt.close(fig)

        return {
            "success": True,
            "output_path": str(output_path),
            "resolution": resolution,
            "bounds": bounds,
            "value_range": data["value_range"]
        }

    except ImportError as e:
        return {"success": False, "error": f"Missing dependency: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
