"""
Hero Image Generation using ParaView

Generates publication-quality 3D visualization of flow around the wheel
using ParaView's Python API (pvpython) in headless mode.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional
import shutil


def check_paraview_available() -> Tuple[bool, str]:
    """Check if ParaView is available for rendering."""
    try:
        result = subprocess.run(
            ["pvpython", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "pvpython not found"
    except FileNotFoundError:
        return False, "pvpython not installed"
    except subprocess.TimeoutExpired:
        return False, "pvpython timeout"
    except Exception as e:
        return False, str(e)


def generate_hero_image(case_dir: Path,
                         output_path: Path,
                         width: int = 1920,
                         height: int = 1080,
                         camera_position: Tuple[float, float, float] = (1.5, -2.0, 1.0),
                         focal_point: Tuple[float, float, float] = (0.0, 0.0, 0.3),
                         show_streamlines: bool = True,
                         show_pressure: bool = True) -> dict:
    """
    Generate a hero image showing the flow visualization.

    Uses ParaView in headless mode to render streamlines colored by velocity
    magnitude over the wheel surface colored by pressure.

    Args:
        case_dir: OpenFOAM case directory
        output_path: Path to save the PNG image
        width: Image width in pixels
        height: Image height in pixels
        camera_position: Camera position (x, y, z)
        focal_point: Camera focal point (x, y, z)
        show_streamlines: Include streamline visualization
        show_pressure: Color wheel surface by pressure

    Returns:
        dict with status and output path
    """
    # Check if ParaView is available
    available, msg = check_paraview_available()
    if not available:
        return {
            "success": False,
            "error": f"ParaView not available: {msg}",
            "fallback": "Use OpenFOAM postProcess for basic visualization"
        }

    # Create the ParaView Python script
    pvscript = f'''
import sys
sys.path.insert(0, '/usr/lib/paraview')

from paraview.simple import *

# Disable automatic color bar addition
paraview.simple._DisableFirstRenderCameraReset()

# Create OpenFOAM reader
case_file = "{case_dir}/case.foam"

# Create empty .foam file if it doesn't exist
import os
if not os.path.exists(case_file):
    with open(case_file, 'w') as f:
        pass

foam = OpenFOAMReader(FileName=case_file)
foam.MeshRegions = ['internalMesh', 'wheel']
foam.CellArrays = ['U', 'p']

# Update to latest timestep
foam.UpdatePipeline()
animationScene = GetAnimationScene()
animationScene.GoToLast()

# Get render view
view = GetActiveViewOrCreate('RenderView')
view.ViewSize = [{width}, {height}]
view.Background = [0.1, 0.1, 0.15]  # Dark background

# Camera setup
view.CameraPosition = [{camera_position[0]}, {camera_position[1]}, {camera_position[2]}]
view.CameraFocalPoint = [{focal_point[0]}, {focal_point[1]}, {focal_point[2]}]
view.CameraViewUp = [0, 0, 1]
view.CameraParallelScale = 1.0

{"# Create streamlines" if show_streamlines else ""}
{"""
# Streamline source
stream = StreamTracer(Input=foam, SeedType='Point Cloud')
stream.SeedType.Center = [0.0, 0.0, 0.35]
stream.SeedType.Radius = 0.5
stream.SeedType.NumberOfPoints = 150
stream.MaximumStreamlineLength = 4.0
stream.IntegrationDirection = 'FORWARD'

# Streamline display
streamDisplay = Show(stream, view)
streamDisplay.Representation = 'Surface'
streamDisplay.LineWidth = 2.0

# Color by velocity magnitude
ColorBy(streamDisplay, ('POINTS', 'U', 'Magnitude'))
uLUT = GetColorTransferFunction('U')
uLUT.ApplyPreset('Cool to Warm', True)
uLUT.RescaleTransferFunction(0, 20)  # 0-20 m/s

# Add color bar for streamlines
streamColorBar = GetScalarBar(uLUT, view)
streamColorBar.Title = 'Velocity (m/s)'
streamColorBar.ComponentTitle = ''
streamColorBar.Visibility = 1
streamColorBar.Position = [0.85, 0.25]
""" if show_streamlines else ""}

{"# Show wheel surface" if show_pressure else ""}
{"""
# Extract wheel surface
wheelSurface = ExtractBlock(Input=foam)
wheelSurface.Selectors = ['/Root/wheel']

# Wheel display
wheelDisplay = Show(wheelSurface, view)
wheelDisplay.Representation = 'Surface'

# Color by pressure
ColorBy(wheelDisplay, ('CELLS', 'p'))
pLUT = GetColorTransferFunction('p')
pLUT.ApplyPreset('Blue to Red Rainbow', True)
pLUT.RescaleTransferFunction(-100, 100)  # Pressure range

# Wheel color bar
pColorBar = GetScalarBar(pLUT, view)
pColorBar.Title = 'Pressure (Pa)'
pColorBar.Visibility = 1
pColorBar.Position = [0.02, 0.25]
""" if show_pressure else """
# Show wheel as solid gray
wheelSurface = ExtractBlock(Input=foam)
wheelSurface.Selectors = ['/Root/wheel']
wheelDisplay = Show(wheelSurface, view)
wheelDisplay.Representation = 'Surface'
wheelDisplay.DiffuseColor = [0.7, 0.7, 0.7]
"""}

# Add ground plane indicator (optional)
# plane = Plane()
# plane.Origin = [-2, -1.5, 0]
# plane.Point1 = [5, -1.5, 0]
# plane.Point2 = [-2, 1.5, 0]
# planeDisplay = Show(plane, view)
# planeDisplay.Representation = 'Surface'
# planeDisplay.DiffuseColor = [0.3, 0.3, 0.3]
# planeDisplay.Opacity = 0.5

# Render and save
Render()
SaveScreenshot("{output_path}", view, ImageResolution=[{width}, {height}])

print("Hero image saved to {output_path}")
'''

    # Write script to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(pvscript)
        script_path = f.name

    try:
        # Ensure case.foam file exists
        foam_file = case_dir / "case.foam"
        if not foam_file.exists():
            foam_file.touch()

        # Run ParaView in headless mode
        result = subprocess.run(
            ["pvpython", script_path],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=case_dir
        )

        # Clean up script
        Path(script_path).unlink()

        if result.returncode == 0 and output_path.exists():
            return {
                "success": True,
                "output_path": str(output_path),
                "width": width,
                "height": height
            }
        else:
            return {
                "success": False,
                "error": result.stderr or "Unknown error",
                "stdout": result.stdout
            }

    except subprocess.TimeoutExpired:
        Path(script_path).unlink()
        return {"success": False, "error": "ParaView rendering timeout"}
    except Exception as e:
        if Path(script_path).exists():
            Path(script_path).unlink()
        return {"success": False, "error": str(e)}


def generate_simple_hero_image(case_dir: Path, output_path: Path) -> dict:
    """
    Generate a simple hero image using matplotlib.

    Fallback when ParaView is not available. Creates a 2D visualization
    of the pressure field from the Y=0 slice.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        from scipy.interpolate import griddata

        # Look for VTK slice data in postProcessing
        post_dir = case_dir / "postProcessing"
        vtk_file = None

        # Find a Y-slice VTK file
        for f in post_dir.rglob("*.vtk"):
            fname = f.name.lower()
            if 'yslice' in fname or 'y-slice' in fname or 'y=0' in fname:
                vtk_file = f
                break

        # If no Y-slice, try any VTK file
        if not vtk_file:
            for f in post_dir.rglob("*.vtk"):
                vtk_file = f
                break

        if not vtk_file:
            # Try to generate slice data by reading forceCoeffs
            return generate_placeholder_hero_image(case_dir, output_path)

        # Parse VTK file
        from backend.visualization.pressure_slices import parse_vtk_file
        data = parse_vtk_file(vtk_file)

        if not data or "error" in data or not data.get("points"):
            return generate_placeholder_hero_image(case_dir, output_path)

        points = np.array(data["points"])
        values = np.array(data["values"])
        bounds = data["bounds"]

        # Determine slice orientation
        x_var = np.var(points[:, 0])
        y_var = np.var(points[:, 1])
        z_var = np.var(points[:, 2])

        min_var = min(x_var, y_var, z_var)
        if min_var == y_var:
            # XZ plane slice (side view)
            h_coord = points[:, 0]
            v_coord = points[:, 2]
            h_label, v_label = 'X (m)', 'Z (m)'
            h_bounds = (bounds["x_min"], bounds["x_max"])
            v_bounds = (bounds["z_min"], bounds["z_max"])
        else:
            # Default XZ view
            h_coord = points[:, 0]
            v_coord = points[:, 2]
            h_label, v_label = 'X (m)', 'Z (m)'
            h_bounds = (bounds["x_min"], bounds["x_max"])
            v_bounds = (bounds["z_min"], bounds["z_max"])

        # Create regular grid
        resolution = 300
        hi = np.linspace(h_bounds[0], h_bounds[1], resolution)
        vi = np.linspace(v_bounds[0], v_bounds[1], resolution)
        hi_grid, vi_grid = np.meshgrid(hi, vi)

        # Interpolate values to grid
        grid_values = griddata((h_coord, v_coord), values,
                               (hi_grid, vi_grid), method='linear')

        # Create figure
        fig, ax = plt.subplots(figsize=(16, 9), facecolor='#0f1419')
        ax.set_facecolor('#0f1419')

        # Plot pressure contour
        v_min, v_max = data["value_range"]["min"], data["value_range"]["max"]

        # Center colormap around zero
        if v_min < 0 < v_max:
            v_abs = max(abs(v_min), abs(v_max))
            v_min, v_max = -v_abs, v_abs

        im = ax.pcolormesh(hi_grid, vi_grid, grid_values,
                           cmap='RdBu_r', vmin=v_min, vmax=v_max,
                           shading='auto')

        # Add colorbar
        cbar = plt.colorbar(im, ax=ax, label='Pressure (Pa)', shrink=0.8)
        cbar.ax.yaxis.label.set_color('#a0a0b0')
        cbar.ax.tick_params(colors='#a0a0b0')

        # Style
        ax.set_xlabel(h_label, color='#a0a0b0', fontsize=12)
        ax.set_ylabel(v_label, color='#a0a0b0', fontsize=12)
        ax.tick_params(colors='#a0a0b0')
        ax.set_aspect('equal')

        # Title with job info
        job_id = case_dir.name
        ax.set_title(f'Flow Visualization - {job_id}',
                     color='#ffffff', fontsize=16, pad=20)

        # Add WheelFlow branding
        fig.text(0.02, 0.02, 'Generated by WheelFlow CFD',
                 color='#606070', fontsize=10, alpha=0.7)

        # Save
        plt.tight_layout()
        plt.savefig(output_path, dpi=120, facecolor='#0f1419',
                    bbox_inches='tight', pad_inches=0.2)
        plt.close(fig)

        return {
            "success": True,
            "output_path": str(output_path),
            "method": "matplotlib_slice",
            "source_file": str(vtk_file)
        }

    except ImportError as e:
        return {"success": False, "error": f"Missing dependency: {e}"}
    except Exception as e:
        return generate_placeholder_hero_image(case_dir, output_path)


def generate_placeholder_hero_image(case_dir: Path, output_path: Path) -> dict:
    """
    Generate a placeholder hero image with basic info when no data available.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        # Create figure
        fig, ax = plt.subplots(figsize=(16, 9), facecolor='#0f1419')
        ax.set_facecolor('#0f1419')

        # Draw placeholder content
        ax.text(0.5, 0.6, 'Flow Visualization',
                ha='center', va='center', fontsize=32,
                color='#ffffff', transform=ax.transAxes)

        job_id = case_dir.name
        ax.text(0.5, 0.45, f'Job: {job_id}',
                ha='center', va='center', fontsize=18,
                color='#a0a0b0', transform=ax.transAxes)

        ax.text(0.5, 0.3, 'Pressure slice data not available',
                ha='center', va='center', fontsize=14,
                color='#606070', transform=ax.transAxes)

        ax.text(0.5, 0.2, 'Run postprocessing to generate visualization',
                ha='center', va='center', fontsize=12,
                color='#606070', transform=ax.transAxes)

        # Draw wheel icon
        circle = plt.Circle((0.5, 0.75), 0.08, fill=False,
                            color='#1d9bf0', linewidth=2,
                            transform=ax.transAxes)
        ax.add_patch(circle)
        inner_circle = plt.Circle((0.5, 0.75), 0.02, fill=False,
                                  color='#1d9bf0', linewidth=2,
                                  transform=ax.transAxes)
        ax.add_patch(inner_circle)

        # Style
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')

        # Branding
        fig.text(0.02, 0.02, 'Generated by WheelFlow CFD',
                 color='#606070', fontsize=10, alpha=0.7)

        # Save
        plt.savefig(output_path, dpi=120, facecolor='#0f1419',
                    bbox_inches='tight', pad_inches=0)
        plt.close(fig)

        return {
            "success": True,
            "output_path": str(output_path),
            "method": "placeholder",
            "note": "No pressure slice data available"
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_pressure_contour_image(case_dir: Path,
                                     output_path: Path,
                                     slice_position: float = 0.0,
                                     field: str = "p") -> dict:
    """
    Generate a 2D pressure contour image at a specified slice position.

    Uses matplotlib for simpler rendering without ParaView dependency.
    """
    try:
        # Check for sample data files
        sample_dir = case_dir / "postProcessing" / "sample"

        # This would parse VTK slice data and render with matplotlib
        # Implementation depends on having pressure slice data available

        return {
            "success": False,
            "error": "Pressure contour generation not yet implemented",
            "suggestion": "Run with pressure slices enabled in controlDict"
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
