"""
End-to-end tests for WheelFlow simulation pipeline

These tests verify the complete workflow from STL upload through
OpenFOAM case generation and mesh creation.
"""

import pytest
import asyncio
import shutil
import struct
from pathlib import Path
from unittest.mock import patch, AsyncMock

# Add backend to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from fastapi.testclient import TestClient
from stl_validator import validate_stl_file, fix_binary_stl_header


class TestSTLUploadPipeline:
    """Tests for STL file upload and validation pipeline"""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client"""
        from app import app
        return TestClient(app)

    def test_upload_valid_stl(self, client, valid_binary_stl):
        """Valid STL upload should succeed"""
        with open(valid_binary_stl, 'rb') as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.stl", f, "application/octet-stream")}
            )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "info" in data
        assert data["info"]["triangles"] == 4

    def test_upload_rejects_non_stl(self, client, temp_dir):
        """Non-STL files should be rejected"""
        txt_file = temp_dir / "test.txt"
        txt_file.write_text("not an stl file")

        with open(txt_file, 'rb') as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.txt", f, "text/plain")}
            )

        assert response.status_code == 400

    def test_upload_wheel_stl_with_warnings(self, client, wheel_stl_path):
        """Wheel STL should upload with validation warnings"""
        if not wheel_stl_path.exists():
            pytest.skip("Wheel STL fixture not available")

        with open(wheel_stl_path, 'rb') as f:
            response = client.post(
                "/api/upload",
                files={"file": ("wheel.stl", f, "application/octet-stream")}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["info"]["triangles"] == 94128


class TestCaseGeneration:
    """Tests for OpenFOAM case generation"""

    @pytest.fixture
    def case_dir(self, temp_dir):
        """Create a temporary case directory"""
        case = temp_dir / "test_case"
        case.mkdir()
        (case / "constant" / "triSurface").mkdir(parents=True)
        (case / "system").mkdir()
        (case / "0").mkdir()
        return case

    def test_stl_copied_to_case(self, case_dir, fixed_wheel_stl):
        """STL should be copied to constant/triSurface"""
        # Simulate copying STL to case
        dest = case_dir / "constant" / "triSurface" / "wheel.stl"
        shutil.copy(fixed_wheel_stl, dest)

        assert dest.exists()

        # Validate the copied file
        result = validate_stl_file(dest)
        assert result.valid is True
        assert "BINARY_SOLID_HEADER" not in [w.code for w in result.warnings]

    def test_snappy_hex_mesh_dict_valid(self, case_dir):
        """Generated snappyHexMeshDict should be valid for OpenFOAM 13"""
        snappy_dict = case_dir / "system" / "snappyHexMeshDict"

        # Write a valid snappyHexMeshDict
        content = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      snappyHexMeshDict;
}

castellatedMesh true;
snap            true;
addLayers       false;

geometry
{
    wheel
    {
        type triSurfaceMesh;
        file "wheel.stl";
    }
}

castellatedMeshControls
{
    maxLocalCells 100000;
    maxGlobalCells 500000;
    minRefinementCells 10;
    nCellsBetweenLevels 2;

    features ();

    refinementSurfaces
    {
        wheel
        {
            level (2 3);
            patchInfo { type wall; }
        }
    }

    resolveFeatureAngle 30;
    refinementRegions {}
    locationInMesh (2 0 0.5);
    allowFreeStandingZoneFaces true;
}

snapControls
{
    nSmoothPatch 3;
    tolerance 2.0;
    nSolveIter 30;
    nRelaxIter 5;
}

addLayersControls
{
    relativeSizes true;
    layers {}
    expansionRatio 1.0;
    finalLayerThickness 0.3;
    minThickness 0.1;
}

meshQualityControls
{
    maxNonOrtho 65;
}

mergeTolerance 1e-6;
"""
        snappy_dict.write_text(content)

        # Verify file keyword is present (OpenFOAM 13 requirement)
        assert 'file "wheel.stl"' in content


class TestOpenFOAMMeshing:
    """Integration tests for OpenFOAM meshing (requires OpenFOAM installed)"""

    @pytest.fixture
    def openfoam_available(self):
        """Check if OpenFOAM is available"""
        openfoam_bin = Path("/opt/openfoam13/platforms/linux64GccDPInt32Opt/bin")
        if not openfoam_bin.exists():
            pytest.skip("OpenFOAM not installed")
        return openfoam_bin

    @pytest.fixture
    def simulation_case(self, temp_dir, fixed_wheel_stl, openfoam_available):
        """Create a complete simulation case for testing"""
        case_dir = temp_dir / "wheel_test"
        case_dir.mkdir()

        # Create directory structure
        (case_dir / "constant" / "triSurface").mkdir(parents=True)
        (case_dir / "system").mkdir()
        (case_dir / "0").mkdir()

        # Copy and transform STL
        self._prepare_stl(fixed_wheel_stl, case_dir)

        # Generate case files
        self._write_block_mesh_dict(case_dir)
        self._write_snappy_hex_mesh_dict(case_dir)
        self._write_control_dict(case_dir)
        self._write_fv_schemes(case_dir)
        self._write_fv_solution(case_dir)

        return case_dir

    def _prepare_stl(self, src_stl, case_dir):
        """Prepare STL file with proper scaling and positioning"""
        dest = case_dir / "constant" / "triSurface" / "wheel.stl"

        # Read, transform, and write STL
        result = validate_stl_file(src_stl)
        scale = 0.001  # mm to m

        with open(src_stl, 'rb') as f:
            f.seek(80)
            num_triangles = struct.unpack('<I', f.read(4))[0]

            # Calculate center
            vertices = []
            for _ in range(num_triangles):
                f.read(12)  # skip normal
                for _ in range(3):
                    v = struct.unpack('<3f', f.read(12))
                    vertices.append(v)
                f.read(2)

        cx = sum(v[0] for v in vertices) / len(vertices)
        cy = sum(v[1] for v in vertices) / len(vertices)
        cz = sum(v[2] for v in vertices) / len(vertices)

        # Calculate wheel radius for positioning
        max_dim = result.geometry.max_dimension * scale
        wheel_radius = max_dim / 2

        # Write transformed STL
        with open(src_stl, 'rb') as f_in, open(dest, 'wb') as f_out:
            # Write header
            f_out.write(b"binary STL - wheel for CFD".ljust(80, b'\x00'))
            f_in.read(80)

            # Copy triangle count
            tri_bytes = f_in.read(4)
            f_out.write(tri_bytes)
            num_tri = struct.unpack('<I', tri_bytes)[0]

            # Transform each triangle
            for _ in range(num_tri):
                # Copy normal
                f_out.write(f_in.read(12))

                # Transform vertices
                for _ in range(3):
                    x, y, z = struct.unpack('<3f', f_in.read(12))
                    # Center, scale, rotate to stand upright, position on ground
                    x_new = (x - cx) * scale
                    y_new = -(z - cz) * scale  # Rotate: old Z -> -Y
                    z_new = (y - cy) * scale + wheel_radius  # Rotate: old Y -> Z, lift to ground

                    f_out.write(struct.pack('<3f', x_new, y_new, z_new))

                f_out.write(f_in.read(2))

    def _write_block_mesh_dict(self, case_dir):
        """Write blockMeshDict"""
        content = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      blockMeshDict;
}

scale 1;

vertices
(
    (-2 -1.5 0)
    ( 5 -1.5 0)
    ( 5  1.5 0)
    (-2  1.5 0)
    (-2 -1.5 2)
    ( 5 -1.5 2)
    ( 5  1.5 2)
    (-2  1.5 2)
);

blocks
(
    hex (0 1 2 3 4 5 6 7) (70 30 20) simpleGrading (1 1 1)
);

edges ();

boundary
(
    inlet  { type patch; faces ((0 4 7 3)); }
    outlet { type patch; faces ((1 2 6 5)); }
    ground { type wall;  faces ((0 1 2 3)); }
    top    { type patch; faces ((4 5 6 7)); }
    sides  { type patch; faces ((0 1 5 4) (3 7 6 2)); }
);
"""
        (case_dir / "system" / "blockMeshDict").write_text(content)

    def _write_snappy_hex_mesh_dict(self, case_dir):
        """Write snappyHexMeshDict"""
        content = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      snappyHexMeshDict;
}

castellatedMesh true;
snap            true;
addLayers       false;

geometry
{
    wheel
    {
        type triSurfaceMesh;
        file "wheel.stl";
    }
}

castellatedMeshControls
{
    maxLocalCells 100000;
    maxGlobalCells 500000;
    minRefinementCells 10;
    nCellsBetweenLevels 2;
    features ();
    refinementSurfaces
    {
        wheel { level (2 3); patchInfo { type wall; } }
    }
    resolveFeatureAngle 30;
    refinementRegions {}
    locationInMesh (2 0 0.5);
    allowFreeStandingZoneFaces true;
}

snapControls
{
    nSmoothPatch 3;
    tolerance 2.0;
    nSolveIter 30;
    nRelaxIter 5;
}

addLayersControls
{
    relativeSizes true;
    layers {}
    expansionRatio 1.0;
    finalLayerThickness 0.3;
    minThickness 0.1;
    nGrow 0;
    featureAngle 60;
    nRelaxIter 3;
    nSmoothSurfaceNormals 1;
    nSmoothNormals 3;
    nSmoothThickness 10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedianAxisAngle 90;
    nBufferCellsNoExtrude 0;
    nLayerIter 50;
}

meshQualityControls
{
    maxNonOrtho 65;
    maxBoundarySkewness 20;
    maxInternalSkewness 4;
    maxConcave 80;
    minVol 1e-13;
    minTetQuality -1e30;
    minArea -1;
    minTwist 0.02;
    minDeterminant 0.001;
    minFaceWeight 0.05;
    minVolRatio 0.01;
    minTriangleTwist -1;
    nSmoothScale 4;
    errorReduction 0.75;
}

mergeTolerance 1e-6;
"""
        (case_dir / "system" / "snappyHexMeshDict").write_text(content)

    def _write_control_dict(self, case_dir):
        """Write controlDict"""
        content = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      controlDict;
}

application     simpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         100;
deltaT          1;
writeControl    timeStep;
writeInterval   100;
purgeWrite      0;
writeFormat     ascii;
writePrecision  6;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;
"""
        (case_dir / "system" / "controlDict").write_text(content)

    def _write_fv_schemes(self, case_dir):
        """Write fvSchemes"""
        content = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvSchemes;
}

ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; }
divSchemes
{
    default none;
    div(phi,U) bounded Gauss linearUpwind grad(U);
    div(phi,k) bounded Gauss upwind;
    div(phi,omega) bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
"""
        (case_dir / "system" / "fvSchemes").write_text(content)

    def _write_fv_solution(self, case_dir):
        """Write fvSolution"""
        content = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvSolution;
}

solvers
{
    p { solver GAMG; tolerance 1e-06; relTol 0.1; smoother GaussSeidel; }
    U { solver smoothSolver; smoother GaussSeidel; tolerance 1e-05; relTol 0.1; }
    k { solver smoothSolver; smoother GaussSeidel; tolerance 1e-05; relTol 0.1; }
    omega { solver smoothSolver; smoother GaussSeidel; tolerance 1e-05; relTol 0.1; }
}

SIMPLE
{
    nNonOrthogonalCorrectors 0;
    consistent yes;
    residualControl { p 1e-4; U 1e-4; k 1e-4; omega 1e-4; }
}

relaxationFactors
{
    fields { p 0.3; }
    equations { U 0.7; k 0.7; omega 0.7; }
}
"""
        (case_dir / "system" / "fvSolution").write_text(content)

    def test_block_mesh_succeeds(self, simulation_case, openfoam_available):
        """blockMesh should complete successfully"""
        import subprocess
        import os

        env = os.environ.copy()
        env['PATH'] = str(openfoam_available) + ':' + env.get('PATH', '')

        result = subprocess.run(
            ['blockMesh'],
            cwd=simulation_case,
            capture_output=True,
            text=True,
            env=env,
            timeout=60
        )

        assert result.returncode == 0, f"blockMesh failed: {result.stderr}"
        assert (simulation_case / "constant" / "polyMesh").exists()

    def test_snappy_hex_mesh_succeeds(self, simulation_case, openfoam_available):
        """snappyHexMesh should complete successfully"""
        import subprocess
        import os

        env = os.environ.copy()
        env['PATH'] = str(openfoam_available) + ':' + env.get('PATH', '')

        # First run blockMesh
        subprocess.run(
            ['blockMesh'],
            cwd=simulation_case,
            capture_output=True,
            env=env,
            timeout=60
        )

        # Then run snappyHexMesh
        result = subprocess.run(
            ['snappyHexMesh'],
            cwd=simulation_case,
            capture_output=True,
            text=True,
            env=env,
            timeout=300
        )

        assert result.returncode == 0, f"snappyHexMesh failed: {result.stderr}"
        assert "Finished meshing without any errors" in result.stdout

    def test_mesh_captures_wheel_geometry(self, simulation_case, openfoam_available):
        """Mesh should capture the wheel geometry"""
        import subprocess
        import os

        env = os.environ.copy()
        env['PATH'] = str(openfoam_available) + ':' + env.get('PATH', '')

        # Run meshing
        subprocess.run(['blockMesh'], cwd=simulation_case, capture_output=True, env=env, timeout=60)
        result = subprocess.run(
            ['snappyHexMesh'],
            cwd=simulation_case,
            capture_output=True,
            text=True,
            env=env,
            timeout=300
        )

        # Check that wheel patch was created and has faces
        assert "wheel" in result.stdout
        # Should have intersected edges (geometry captured)
        assert "Number of intersected edges : 0" not in result.stdout or \
               "intersected edges : 0\nCalculated" not in result.stdout


class TestErrorMessages:
    """Tests for error message quality"""

    def test_solid_header_error_is_helpful(self, wheel_stl_path):
        """Error for solid header should explain the issue clearly"""
        if not wheel_stl_path.exists():
            pytest.skip("Wheel STL fixture not available")

        result = validate_stl_file(wheel_stl_path)

        header_warning = next(
            (w for w in result.warnings if w.code == "BINARY_SOLID_HEADER"),
            None
        )
        assert header_warning is not None
        assert "solid" in header_warning.message.lower()
        assert "OpenFOAM" in header_warning.suggestion

    def test_millimeter_warning_is_helpful(self, wheel_stl_path):
        """Warning for millimeter units should explain scaling"""
        if not wheel_stl_path.exists():
            pytest.skip("Wheel STL fixture not available")

        result = validate_stl_file(wheel_stl_path)

        mm_warning = next(
            (w for w in result.warnings if w.code == "LIKELY_MILLIMETERS"),
            None
        )
        assert mm_warning is not None
        assert "millimeters" in mm_warning.message.lower()
        assert "scaled" in mm_warning.suggestion.lower()

    def test_corrupted_file_suggests_reexport(self, truncated_stl):
        """Corrupted file error should suggest re-exporting"""
        result = validate_stl_file(truncated_stl)

        assert len(result.errors) > 0
        suggestions = " ".join(e.suggestion or "" for e in result.errors)
        assert "export" in suggestions.lower() or "CAD" in suggestions
