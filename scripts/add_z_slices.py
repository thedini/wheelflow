#!/usr/bin/env python3
"""
Add Z-direction pressure slices to existing OpenFOAM cases.

Usage:
    python scripts/add_z_slices.py <case_dir>
    python scripts/add_z_slices.py cases/7a430d2b_00

This script:
1. Updates the controlDict to add Z-slice function objects
2. Runs OpenFOAM post-processing to generate the slice data
"""

import sys
import subprocess
from pathlib import Path

Z_SLICES_FUNCTION = """
    zSlices
    {
        type            surfaces;
        libs            ("libsampling.so");
        writeControl    writeTime;
        surfaceFormat   vtk;
        fields          (p U);
        interpolationScheme cellPoint;

        surfaces
        {
            zSlice_ground
            {
                type            cuttingPlane;
                planeType       pointAndNormal;
                point           (0 0 0.01);
                normal          (0 0 1);
                interpolate     true;
            }
            zSlice_hub
            {
                type            cuttingPlane;
                planeType       pointAndNormal;
                point           (0 0 0.35);
                normal          (0 0 1);
                interpolate     true;
            }
            zSlice_top
            {
                type            cuttingPlane;
                planeType       pointAndNormal;
                point           (0 0 0.68);
                normal          (0 0 1);
                interpolate     true;
            }
        }
    }
"""


def add_z_slices_to_case(case_dir: Path):
    """Add Z-slice function objects to an existing case."""
    control_dict = case_dir / "system" / "controlDict"

    if not control_dict.exists():
        print(f"Error: {control_dict} not found")
        return False

    # Read current controlDict
    content = control_dict.read_text()

    # Check if zSlices already exists
    if "zSlice" in content:
        print("Z-slices already configured in controlDict")
        return True

    # Find the functions section and add zSlices before the closing brace
    # Look for the last closing brace of the functions block
    if "functions" not in content:
        print("Error: No functions section in controlDict")
        return False

    # Find where to insert (before the final closing braces)
    # Simple approach: find "pressureSlices" block end and add after
    lines = content.split('\n')
    new_lines = []
    inserted = False
    brace_count = 0
    in_functions = False

    for i, line in enumerate(lines):
        new_lines.append(line)

        if 'functions' in line and '{' in line:
            in_functions = True

        if in_functions:
            brace_count += line.count('{') - line.count('}')

            # Insert before the final closing brace of functions
            if brace_count == 1 and '}' in line and not inserted:
                # Check if next line closes functions
                if i + 1 < len(lines) and lines[i + 1].strip() == '}':
                    new_lines.append(Z_SLICES_FUNCTION)
                    inserted = True

    if not inserted:
        # Fallback: insert before final }
        for i in range(len(new_lines) - 1, -1, -1):
            if new_lines[i].strip() == '}':
                new_lines.insert(i, Z_SLICES_FUNCTION)
                break

    # Write updated controlDict
    control_dict.write_text('\n'.join(new_lines))
    print(f"Updated {control_dict} with Z-slice function objects")
    return True


def create_z_slices_dict(case_dir: Path):
    """Create a standalone zSlicesDict file for post-processing."""
    z_slices_dict = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      zSlicesDict;
}

zSlices
{
    type            surfaces;
    libs            ("libsampling.so");
    writeControl    writeTime;
    surfaceFormat   vtk;
    fields          (p U);
    interpolationScheme cellPoint;

    surfaces
    {
        zSlice_ground
        {
            type            cuttingPlane;
            planeType       pointAndNormal;
            point           (0 0 0.01);
            normal          (0 0 1);
            interpolate     true;
        }
        zSlice_hub
        {
            type            cuttingPlane;
            planeType       pointAndNormal;
            point           (0 0 0.35);
            normal          (0 0 1);
            interpolate     true;
        }
        zSlice_top
        {
            type            cuttingPlane;
            planeType       pointAndNormal;
            point           (0 0 0.68);
            normal          (0 0 1);
            interpolate     true;
        }
    }
}
"""
    dict_path = case_dir / "system" / "zSlicesDict"
    dict_path.write_text(z_slices_dict)
    print(f"Created {dict_path}")
    return dict_path


def run_postprocess(case_dir: Path):
    """Run OpenFOAM post-processing to generate slice data."""
    print(f"Running post-processing in {case_dir}...")

    # Create standalone function dict
    create_z_slices_dict(case_dir)

    # Run foamPostProcess with the dict file
    cmd = f"""
    source /opt/openfoam13/etc/bashrc 2>/dev/null || source /opt/openfoam12/etc/bashrc 2>/dev/null
    cd {case_dir}
    foamPostProcess -dict system/zSlicesDict -latestTime
    """

    result = subprocess.run(
        ['bash', '-c', cmd],
        capture_output=True,
        text=True
    )

    print(f"Post-processing output:\n{result.stdout}")
    if result.stderr:
        print(f"Post-processing messages:\n{result.stderr}")

    # Check if output was created regardless of return code
    z_slices_dir = case_dir / "postProcessing" / "zSlices"
    if z_slices_dir.exists() and any(z_slices_dir.rglob("*.vtk")):
        print("Post-processing complete!")
        return True

    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/add_z_slices.py <case_dir>")
        print("Example: python scripts/add_z_slices.py cases/7a430d2b_00")
        sys.exit(1)

    case_dir = Path(sys.argv[1])

    if not case_dir.exists():
        print(f"Error: Case directory {case_dir} does not exist")
        sys.exit(1)

    print(f"Adding Z-slices to case: {case_dir}")

    # Step 1: Update controlDict
    if not add_z_slices_to_case(case_dir):
        sys.exit(1)

    # Step 2: Run post-processing
    if not run_postprocess(case_dir):
        print("Warning: Post-processing failed. You may need to run manually:")
        print(f"  cd {case_dir}")
        print("  simpleFoam -postProcess -func zSlices -latestTime")
        sys.exit(1)

    # Check results
    z_slices_dir = case_dir / "postProcessing" / "zSlices"
    if z_slices_dir.exists():
        print(f"\nZ-slices generated in: {z_slices_dir}")
        for vtk in z_slices_dir.rglob("*.vtk"):
            print(f"  - {vtk.name}")
    else:
        print("\nWarning: zSlices directory not created. Check OpenFOAM output.")


if __name__ == "__main__":
    main()
