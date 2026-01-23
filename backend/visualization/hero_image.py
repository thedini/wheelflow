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
    Generate a simple hero image using OpenFOAM's built-in postProcessing.

    Fallback when ParaView is not available.
    """
    # Use foamToVTK to convert, then use matplotlib/vtk for rendering
    # This is a simpler alternative that doesn't require ParaView

    try:
        # Check if VTK files exist
        vtk_dir = case_dir / "VTK"
        if not vtk_dir.exists():
            # Run foamToVTK
            import subprocess
            env = get_openfoam_env()  # Would need to import this
            result = subprocess.run(
                ["foamToVTK", "-latestTime"],
                cwd=case_dir,
                capture_output=True,
                timeout=120
            )

        # For now, return a placeholder
        return {
            "success": False,
            "error": "Simple rendering not yet implemented",
            "suggestion": "Install ParaView for full visualization support"
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
