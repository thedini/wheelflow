"""
3D Pressure Surface Export for Three.js Visualization

Exports the wheel surface with pressure values for interactive
3D visualization in the browser using Three.js.
"""

import struct
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re


def parse_openfoam_boundary_mesh(case_dir: Path, patch_name: str = "wheel") -> Optional[Dict]:
    """
    Parse OpenFOAM boundary mesh to extract wheel surface geometry.

    Args:
        case_dir: OpenFOAM case directory
        patch_name: Name of the patch to extract

    Returns:
        dict with vertices, faces, and face centers
    """
    # Find the polyMesh directory (could be in constant or latest time)
    poly_mesh = case_dir / "constant" / "polyMesh"
    if not poly_mesh.exists():
        # Try reconstructed mesh
        time_dirs = sorted([d for d in case_dir.iterdir() if d.is_dir() and d.name.replace('.', '').isdigit()])
        if time_dirs:
            poly_mesh = time_dirs[-1] / "polyMesh"

    if not poly_mesh.exists():
        return None

    try:
        # Read boundary file to find patch faces
        boundary_file = poly_mesh / "boundary"
        if not boundary_file.exists():
            return None

        boundary_content = boundary_file.read_text()

        # Parse boundary to find wheel patch
        # OpenFOAM format: patchName { type ...; nFaces N; startFace S; }
        patch_pattern = rf'{patch_name}\s*\{{\s*type\s+(\w+);\s*nFaces\s+(\d+);\s*startFace\s+(\d+);'
        match = re.search(patch_pattern, boundary_content)

        if not match:
            return None

        patch_type = match.group(1)
        n_faces = int(match.group(2))
        start_face = int(match.group(3))

        # Read points
        points_file = poly_mesh / "points"
        points = parse_openfoam_vector_file(points_file)

        # Read faces
        faces_file = poly_mesh / "faces"
        all_faces = parse_openfoam_faces_file(faces_file)

        # Extract only the patch faces
        patch_faces = all_faces[start_face:start_face + n_faces]

        return {
            "points": points,
            "faces": patch_faces,
            "n_faces": n_faces,
            "patch_name": patch_name,
            "patch_type": patch_type
        }

    except Exception as e:
        return {"error": str(e)}


def parse_openfoam_vector_file(file_path: Path) -> List[Tuple[float, float, float]]:
    """Parse OpenFOAM vector field file (like points)."""
    content = file_path.read_text()

    # Find the data section (after the FoamFile header)
    # OpenFOAM format: N ( (x y z) (x y z) ... )
    data_match = re.search(r'\)\s*(\d+)\s*\((.*)\)', content, re.DOTALL)

    if not data_match:
        # Try alternative format
        lines = content.split('\n')
        points = []
        in_data = False
        for line in lines:
            line = line.strip()
            if line.startswith('(') and not in_data:
                in_data = True
                continue
            if in_data:
                if line == ')':
                    break
                # Parse (x y z) format
                if line.startswith('(') and line.endswith(')'):
                    coords = line[1:-1].split()
                    if len(coords) >= 3:
                        points.append((float(coords[0]), float(coords[1]), float(coords[2])))
        return points

    n_points = int(data_match.group(1))
    data_str = data_match.group(2)

    # Parse individual points
    point_pattern = r'\(([^)]+)\)'
    matches = re.findall(point_pattern, data_str)

    points = []
    for match in matches[:n_points]:
        coords = match.split()
        if len(coords) >= 3:
            points.append((float(coords[0]), float(coords[1]), float(coords[2])))

    return points


def parse_openfoam_faces_file(file_path: Path) -> List[List[int]]:
    """Parse OpenFOAM faces file."""
    content = file_path.read_text()

    # Find data section
    lines = content.split('\n')
    faces = []
    in_data = False
    brace_count = 0

    for line in lines:
        line = line.strip()

        if not in_data:
            # Look for start of face list
            if line.isdigit():
                in_data = True
            continue

        if line == '(':
            brace_count += 1
            continue
        if line == ')':
            brace_count -= 1
            if brace_count <= 0:
                break
            continue

        # Parse face: N(v1 v2 v3 ...)
        match = re.match(r'(\d+)\(([^)]+)\)', line)
        if match:
            n_verts = int(match.group(1))
            verts = [int(v) for v in match.group(2).split()]
            faces.append(verts[:n_verts])

    return faces


def read_pressure_field(case_dir: Path, time: str = "latestTime") -> Optional[Dict]:
    """
    Read pressure field from OpenFOAM results.

    Args:
        case_dir: Case directory
        time: Time step to read ("latestTime" for latest)

    Returns:
        dict with boundary field values
    """
    # Find time directory
    if time == "latestTime":
        time_dirs = sorted([d for d in case_dir.iterdir()
                            if d.is_dir() and d.name.replace('.', '').isdigit()],
                           key=lambda x: float(x.name))
        if not time_dirs:
            return None
        time_dir = time_dirs[-1]
    else:
        time_dir = case_dir / time

    p_file = time_dir / "p"
    if not p_file.exists():
        return None

    try:
        content = p_file.read_text()

        # Parse boundary field values
        # Look for: wheel { type ...; value uniform X; } or value nonuniform List<scalar>
        wheel_pattern = r'wheel\s*\{[^}]*value\s+(uniform\s+[\d.e+-]+|nonuniform\s+List<scalar>[^;]+);'
        match = re.search(wheel_pattern, content, re.DOTALL)

        if match:
            value_str = match.group(1)
            if value_str.startswith('uniform'):
                # Single value for all faces
                value = float(value_str.split()[1])
                return {"type": "uniform", "value": value}
            else:
                # Non-uniform - parse list
                # Format: nonuniform List<scalar> N ( v1 v2 ... )
                list_pattern = r'List<scalar>\s*(\d+)\s*\(([^)]+)\)'
                list_match = re.search(list_pattern, value_str)
                if list_match:
                    n = int(list_match.group(1))
                    values = [float(v) for v in list_match.group(2).split()]
                    return {"type": "nonuniform", "values": values[:n], "count": n}

        return None

    except Exception as e:
        return {"error": str(e)}


def export_pressure_surface_ply(case_dir: Path,
                                 output_path: Path,
                                 patch_name: str = "wheel",
                                 field: str = "p") -> Dict:
    """
    Export wheel surface as PLY file with pressure as vertex colors.

    PLY format is well-supported by Three.js PLYLoader.

    Args:
        case_dir: OpenFOAM case directory
        output_path: Path to save PLY file
        patch_name: Patch to export
        field: Field to use for coloring (p, U magnitude, etc.)

    Returns:
        dict with status and file info
    """
    # Get mesh
    mesh = parse_openfoam_boundary_mesh(case_dir, patch_name)
    if not mesh or "error" in mesh:
        return {"success": False, "error": mesh.get("error", "Could not read mesh")}

    # Get pressure field
    pressure = read_pressure_field(case_dir)

    # Prepare vertex colors based on pressure
    # Map pressure to RGB using a colormap
    def pressure_to_color(p: float, p_min: float = -200, p_max: float = 200) -> Tuple[int, int, int]:
        """Map pressure value to RGB color (blue-white-red diverging)."""
        # Normalize to [0, 1]
        t = max(0, min(1, (p - p_min) / (p_max - p_min)))

        if t < 0.5:
            # Blue to white
            r = int(255 * (t * 2))
            g = int(255 * (t * 2))
            b = 255
        else:
            # White to red
            r = 255
            g = int(255 * (2 - t * 2))
            b = int(255 * (2 - t * 2))

        return (r, g, b)

    points = mesh["points"]
    faces = mesh["faces"]

    # For PLY, we need to output vertex positions with colors
    # Since pressure is face-centered in OpenFOAM, we'll use face colors

    # Write PLY file
    try:
        # Collect unique vertices used by patch faces
        used_vertices = set()
        for face in faces:
            used_vertices.update(face)

        # Create vertex index mapping
        vertex_map = {v: i for i, v in enumerate(sorted(used_vertices))}
        used_points = [points[v] for v in sorted(used_vertices)]

        # Default colors (gray) if no pressure data
        if pressure and pressure.get("type") == "nonuniform":
            p_values = pressure["values"]
            p_min = min(p_values)
            p_max = max(p_values)
        else:
            p_values = None
            p_min, p_max = -100, 100

        # Write binary PLY
        with open(output_path, 'wb') as f:
            # Header
            header = f"""ply
format binary_little_endian 1.0
element vertex {len(used_points)}
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
element face {len(faces)}
property list uchar int vertex_indices
end_header
"""
            f.write(header.encode('ascii'))

            # Write vertices with colors
            for i, (x, y, z) in enumerate(used_points):
                # Get color - for now use gray since we have face-centered data
                r, g, b = 180, 180, 180
                f.write(struct.pack('<fffBBB', x, y, z, r, g, b))

            # Write faces
            for i, face in enumerate(faces):
                n_verts = len(face)
                mapped_verts = [vertex_map[v] for v in face]

                # For triangular faces
                if n_verts == 3:
                    f.write(struct.pack('<B', 3))
                    f.write(struct.pack('<iii', *mapped_verts))
                elif n_verts == 4:
                    # Split quad into two triangles
                    f.write(struct.pack('<B', 3))
                    f.write(struct.pack('<iii', mapped_verts[0], mapped_verts[1], mapped_verts[2]))
                    f.write(struct.pack('<B', 3))
                    f.write(struct.pack('<iii', mapped_verts[0], mapped_verts[2], mapped_verts[3]))
                else:
                    # Fan triangulation for polygons
                    for j in range(1, n_verts - 1):
                        f.write(struct.pack('<B', 3))
                        f.write(struct.pack('<iii', mapped_verts[0], mapped_verts[j], mapped_verts[j + 1]))

        return {
            "success": True,
            "output_path": str(output_path),
            "n_vertices": len(used_points),
            "n_faces": len(faces),
            "pressure_range": [p_min, p_max] if p_values else None
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def export_pressure_surface_json(case_dir: Path,
                                  output_path: Path,
                                  patch_name: str = "wheel") -> Dict:
    """
    Export wheel surface as JSON for direct use in Three.js.

    JSON format includes:
    - vertices: flat array of [x, y, z, x, y, z, ...]
    - indices: flat array of face indices
    - pressures: array of pressure values per face

    This format is efficient for Three.js BufferGeometry.
    """
    mesh = parse_openfoam_boundary_mesh(case_dir, patch_name)
    if not mesh or "error" in mesh:
        return {"success": False, "error": mesh.get("error", "Could not read mesh")}

    pressure = read_pressure_field(case_dir)

    points = mesh["points"]
    faces = mesh["faces"]

    # Collect unique vertices
    used_vertices = set()
    for face in faces:
        used_vertices.update(face)

    vertex_map = {v: i for i, v in enumerate(sorted(used_vertices))}
    used_points = [points[v] for v in sorted(used_vertices)]

    # Flatten vertices
    vertices = []
    for x, y, z in used_points:
        vertices.extend([x, y, z])

    # Flatten face indices (triangulated)
    indices = []
    for face in faces:
        mapped = [vertex_map[v] for v in face]
        if len(mapped) == 3:
            indices.extend(mapped)
        elif len(mapped) == 4:
            # Quad to triangles
            indices.extend([mapped[0], mapped[1], mapped[2]])
            indices.extend([mapped[0], mapped[2], mapped[3]])
        else:
            # Fan triangulation
            for j in range(1, len(mapped) - 1):
                indices.extend([mapped[0], mapped[j], mapped[j + 1]])

    # Pressure values
    pressures = []
    if pressure and pressure.get("type") == "nonuniform":
        pressures = pressure["values"]
    elif pressure and pressure.get("type") == "uniform":
        pressures = [pressure["value"]] * len(faces)

    result = {
        "vertices": vertices,
        "indices": indices,
        "pressures": pressures,
        "n_vertices": len(used_points),
        "n_triangles": len(indices) // 3,
        "pressure_range": [min(pressures), max(pressures)] if pressures else None
    }

    # Write JSON
    try:
        with open(output_path, 'w') as f:
            json.dump(result, f)

        return {
            "success": True,
            "output_path": str(output_path),
            **{k: v for k, v in result.items() if k != "vertices" and k != "indices" and k != "pressures"}
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
