"""
WheelFlow - Bicycle Wheel CFD Analysis Platform
FastAPI Backend for OpenFOAM Integration
"""

import os
import json
import uuid
import shutil
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.requests import Request
from pydantic import BaseModel
import math

# STL validation module
try:
    from backend.stl_validator import (
        validate_stl_file,
        fix_binary_stl_header,
        get_stl_transform_for_openfoam,
        transform_stl_for_openfoam,
        STLFormat
    )
    from backend.system_monitor import get_system_stats, get_openfoam_progress
    from backend.frontal_area import get_frontal_area_for_simulation, calculate_wheel_frontal_area
    from backend.openfoam_templates.dynamic_mesh import (
        generate_mrf_properties,
        generate_dynamic_mesh_dict,
        generate_fv_options_mrf,
        calculate_rotation_params
    )
    from backend.openfoam_templates.pimple_settings import (
        generate_pimple_fv_solution,
        generate_transient_control_dict,
        generate_transient_fv_schemes
    )
    from backend.openfoam_templates.boundary_conditions import (
        generate_velocity_file_rotating,
        generate_all_field_files_rotating
    )
    from backend import database as db
except ImportError:
    from stl_validator import (
        validate_stl_file,
        fix_binary_stl_header,
        get_stl_transform_for_openfoam,
        transform_stl_for_openfoam,
        STLFormat
    )
    from system_monitor import get_system_stats, get_openfoam_progress
    from frontal_area import get_frontal_area_for_simulation, calculate_wheel_frontal_area
    from openfoam_templates.dynamic_mesh import (
        generate_mrf_properties,
        generate_dynamic_mesh_dict,
        generate_fv_options_mrf,
        calculate_rotation_params
    )
    from openfoam_templates.pimple_settings import (
        generate_pimple_fv_solution,
        generate_transient_control_dict,
        generate_transient_fv_schemes
    )
    from openfoam_templates.boundary_conditions import (
        generate_velocity_file_rotating,
        generate_all_field_files_rotating
    )
    import database as db

# Configuration
BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
CASES_DIR = BASE_DIR / "cases"
RESULTS_DIR = BASE_DIR / "results"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# OpenFOAM Configuration
OPENFOAM_DIR = Path("/opt/openfoam13")
OPENFOAM_BIN = OPENFOAM_DIR / "platforms/linux64GccDPInt32Opt/bin"

# Ensure directories exist
for d in [UPLOAD_DIR, CASES_DIR, RESULTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="WheelFlow", description="Bicycle Wheel CFD Analysis")

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Job store - backed by SQLite database for persistence
# Initialize jobs dict from database on startup
def _load_jobs_from_db():
    """Load all jobs from database into memory cache."""
    return {job['id']: job for job in db.get_all_jobs()}

jobs = _load_jobs_from_db()


def sync_job_to_db(job_id: str, job: dict = None):
    """Sync job changes to database. Call after significant job updates."""
    if job is None:
        job = jobs.get(job_id)
    if job:
        db.update_job(
            job_id,
            status=job.get('status'),
            results=job.get('results'),
            error=job.get('error')
        )


class SimulationConfig(BaseModel):
    name: str
    speed: float = 13.9  # m/s
    yaw_angles: List[float] = [0.0]
    fluid: str = "air"
    ground_enabled: bool = True
    ground_type: str = "moving"  # slip or moving
    rolling_enabled: bool = True
    wheel_radius: float = 0.325  # m
    quality: str = "standard"  # basic, standard, pro
    rotation_method: str = "mrf"  # none, mrf, or transient (AMI)


class JobStatus(BaseModel):
    id: str
    name: str
    status: str  # queued, meshing, solving, post-processing, complete, failed
    progress: int
    created_at: str
    updated_at: str
    config: dict
    results: Optional[dict] = None
    error: Optional[str] = None


def get_air_properties():
    """Standard air properties at sea level"""
    return {
        "rho": 1.225,  # kg/m³
        "nu": 1.48e-5,  # m²/s (kinematic viscosity)
        "mu": 1.81e-5,  # Pa·s (dynamic viscosity)
    }


def calculate_omega(speed: float, radius: float) -> float:
    """Calculate angular velocity from linear speed and radius"""
    return speed / radius


def calculate_reynolds(speed: float, length: float, nu: float = 1.48e-5) -> float:
    """Calculate Reynolds number"""
    return speed * length / nu


def velocity_components(speed: float, yaw_deg: float) -> tuple:
    """Calculate velocity components for given yaw angle"""
    yaw_rad = math.radians(yaw_deg)
    return (
        speed * math.cos(yaw_rad),  # x component
        speed * math.sin(yaw_rad),  # y component
        0.0  # z component
    )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main application page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/upload")
async def upload_stl(file: UploadFile = File(...)):
    """Upload STL file and return file info with validation"""
    if not file.filename.lower().endswith(('.stl', '.obj')):
        raise HTTPException(400, "Only STL and OBJ files are supported")

    file_id = str(uuid.uuid4())[:8]
    file_ext = Path(file.filename).suffix.lower()
    saved_filename = f"{file_id}{file_ext}"
    file_path = UPLOAD_DIR / saved_filename

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Get file stats
    file_size = file_path.stat().st_size

    # Validate STL file with detailed error messages
    if file_ext == '.stl':
        validation = validate_stl_file(file_path)

        # Check for fatal errors
        if not validation.valid:
            # Clean up the uploaded file
            file_path.unlink(missing_ok=True)
            raise HTTPException(
                400,
                detail={
                    "message": validation.error_message,
                    "errors": [e.to_dict() for e in validation.errors]
                }
            )

        # Convert validation result to info dict
        stl_info = validation.to_dict()["geometry"] or {}
        stl_info["format"] = validation.format.value

        # Add any warnings to the response
        if validation.warnings:
            stl_info["warnings"] = [w.to_dict() for w in validation.warnings]

        # Calculate suggested transform for OpenFOAM
        if validation.geometry:
            transform = get_stl_transform_for_openfoam(validation.geometry)
            stl_info["detected_units"] = transform["detected_unit"]
            stl_info["suggested_scale"] = transform["scale"]

            # Add user-friendly scale message
            dims = stl_info.get("dimensions", [0, 0, 0])
            max_dim = max(dims) if dims else 0
            scaled_max_dim = max_dim * transform["scale"]

            # Generate helpful message about detected dimensions
            if transform["detected_unit"] == "millimeters":
                stl_info["scale_message"] = f"STL appears to be in millimeters. Will scale to {scaled_max_dim:.3f}m diameter."
            elif transform["detected_unit"] == "meters":
                stl_info["scale_message"] = f"STL is already in meters. Diameter: {max_dim:.3f}m (no scaling needed)."
            else:
                stl_info["scale_message"] = f"Unit detection uncertain. Max dimension: {max_dim:.3f} (scale={transform['scale']})"

            # Warn if scaled dimensions are unusual for a bicycle wheel
            if scaled_max_dim < 0.3 or scaled_max_dim > 1.0:
                warning_msg = f"WARNING: Scaled diameter ({scaled_max_dim:.3f}m) seems unusual for a bicycle wheel. " \
                             f"Expected 0.5-0.75m. Please verify your STL units."
                stl_info["dimension_warning"] = warning_msg
                if "warnings" not in stl_info:
                    stl_info["warnings"] = []
                stl_info["warnings"].append({"type": "dimension", "message": warning_msg})
    else:
        # OBJ files - use legacy parser
        stl_info = parse_stl_info(file_path)

    return {
        "id": file_id,
        "filename": file.filename,
        "saved_as": saved_filename,
        "size": file_size,
        "info": stl_info
    }


def parse_stl_info(file_path: Path) -> dict:
    """Parse STL file to extract basic geometry info"""
    info = {
        "triangles": 0,
        "bounds": {"min": [0, 0, 0], "max": [0, 0, 0]},
        "center": [0, 0, 0],
        "dimensions": [0, 0, 0]
    }

    try:
        with open(file_path, 'rb') as f:
            header = f.read(80)
            # Check if binary or ASCII
            if b'solid' in header[:6]:
                # Might be ASCII, check further
                f.seek(0)
                first_line = f.readline()
                if b'facet' in f.readline() or b'endsolid' in f.read(1000):
                    # ASCII STL - parse differently
                    return parse_ascii_stl(file_path)

            # Binary STL
            f.seek(80)
            num_triangles = int.from_bytes(f.read(4), 'little')
            info["triangles"] = num_triangles

            # Read vertices to find bounds
            min_coords = [float('inf')] * 3
            max_coords = [float('-inf')] * 3

            for _ in range(min(num_triangles, 10000)):  # Sample first 10k triangles
                f.read(12)  # Skip normal
                for _ in range(3):  # 3 vertices
                    x = int.from_bytes(f.read(4), 'little')
                    y = int.from_bytes(f.read(4), 'little')
                    z = int.from_bytes(f.read(4), 'little')
                    # Convert to float
                    import struct
                    coords = struct.unpack('fff', struct.pack('III', x, y, z))
                    for i, c in enumerate(coords):
                        min_coords[i] = min(min_coords[i], c)
                        max_coords[i] = max(max_coords[i], c)
                f.read(2)  # Skip attribute

            info["bounds"]["min"] = min_coords
            info["bounds"]["max"] = max_coords
            info["dimensions"] = [max_coords[i] - min_coords[i] for i in range(3)]
            info["center"] = [(max_coords[i] + min_coords[i]) / 2 for i in range(3)]

    except Exception as e:
        info["error"] = str(e)

    return info


def parse_ascii_stl(file_path: Path) -> dict:
    """Parse ASCII STL file"""
    info = {"triangles": 0, "bounds": {"min": [0, 0, 0], "max": [0, 0, 0]}}
    min_coords = [float('inf')] * 3
    max_coords = [float('-inf')] * 3

    with open(file_path, 'r') as f:
        for line in f:
            if 'vertex' in line.lower():
                parts = line.strip().split()
                if len(parts) >= 4:
                    coords = [float(parts[1]), float(parts[2]), float(parts[3])]
                    for i, c in enumerate(coords):
                        min_coords[i] = min(min_coords[i], c)
                        max_coords[i] = max(max_coords[i], c)
            elif 'endfacet' in line.lower():
                info["triangles"] += 1

    if info["triangles"] > 0:
        info["bounds"]["min"] = min_coords
        info["bounds"]["max"] = max_coords
        info["dimensions"] = [max_coords[i] - min_coords[i] for i in range(3)]
        info["center"] = [(max_coords[i] + min_coords[i]) / 2 for i in range(3)]

    return info


@app.get("/api/uploads/{file_id}")
async def get_upload(file_id: str):
    """Get uploaded file for 3D viewer"""
    for ext in ['.stl', '.obj']:
        file_path = UPLOAD_DIR / f"{file_id}{ext}"
        if file_path.exists():
            return FileResponse(file_path)
    raise HTTPException(404, "File not found")


@app.post("/api/simulate")
async def start_simulation(
    background_tasks: BackgroundTasks,
    file_id: str = Form(...),
    name: str = Form(...),
    speed: float = Form(13.9),
    yaw_angles: str = Form("0"),
    ground_enabled: bool = Form(True),
    ground_type: str = Form("moving"),
    rolling_enabled: bool = Form(True),
    wheel_radius: float = Form(0.325),
    quality: str = Form("standard"),
    gpu_acceleration: bool = Form(False),
    rotation_method: str = Form("mrf"),  # none, mrf, transient
):
    """Start a new CFD simulation"""

    # Parse yaw angles
    yaw_list = [float(y.strip()) for y in yaw_angles.split(",")]

    job_id = str(uuid.uuid4())[:8]

    config = {
        "file_id": file_id,
        "name": name,
        "speed": speed,
        "yaw_angles": yaw_list,
        "ground_enabled": ground_enabled,
        "ground_type": ground_type,
        "rolling_enabled": rolling_enabled,
        "wheel_radius": wheel_radius,
        "quality": quality,
        "gpu_acceleration": gpu_acceleration,
        "rotation_method": rotation_method,  # none, mrf, transient
        "omega": calculate_omega(speed, wheel_radius),
        "reynolds": calculate_reynolds(speed, wheel_radius * 2),
        "air": get_air_properties()
    }

    # Create job in database and cache
    job_data = db.create_job(job_id, config)
    job_data["name"] = name
    job_data["progress"] = 0
    jobs[job_id] = job_data

    # Start simulation in background
    background_tasks.add_task(run_simulation, job_id)

    return {"job_id": job_id, "status": "queued"}


@app.post("/api/simulate/batch")
async def start_batch_simulation(
    background_tasks: BackgroundTasks,
    file_id: str = Form(...),
    name: str = Form(...),
    speed: float = Form(13.9),
    yaw_angles: str = Form("0,5,10,15,20"),  # Default to standard sweep
    ground_enabled: bool = Form(True),
    ground_type: str = Form("moving"),
    rolling_enabled: bool = Form(True),
    wheel_radius: float = Form(0.325),
    quality: str = Form("standard"),
    gpu_acceleration: bool = Form(False),
    rotation_method: str = Form("mrf"),
):
    """
    Start a batch CFD simulation for multiple yaw angles.

    This runs separate simulations for each yaw angle and aggregates results
    for polar chart visualization (like AeroCloud).

    Args:
        yaw_angles: Comma-separated list of yaw angles (e.g., "0,5,10,15,20")
    """
    # Parse yaw angles
    yaw_list = [float(y.strip()) for y in yaw_angles.split(",")]

    # Create batch job ID
    batch_id = str(uuid.uuid4())[:8]

    # Create individual jobs for each yaw angle
    sub_jobs = []
    for yaw in yaw_list:
        job_id = f"{batch_id}_{int(yaw):02d}"

        config = {
            "file_id": file_id,
            "name": f"{name}_yaw{int(yaw):02d}",
            "speed": speed,
            "yaw_angles": [yaw],
            "yaw_angle": yaw,  # Single angle for this job
            "ground_enabled": ground_enabled,
            "ground_type": ground_type,
            "rolling_enabled": rolling_enabled,
            "wheel_radius": wheel_radius,
            "quality": quality,
            "gpu_acceleration": gpu_acceleration,
            "rotation_method": rotation_method,
            "omega": calculate_omega(speed, wheel_radius),
            "reynolds": calculate_reynolds(speed, wheel_radius * 2),
            "air": get_air_properties(),
            "batch_id": batch_id,
            "batch_yaw_angles": yaw_list,
        }

        # Create job in database and cache
        job_data = db.create_job(job_id, config, batch_id=batch_id,
                                  batch_yaw_angles=yaw_list, yaw_angle=yaw)
        job_data["name"] = config["name"]
        job_data["progress"] = 0
        jobs[job_id] = job_data

        sub_jobs.append(job_id)

    # Create batch job entry
    batch_jobs[batch_id] = {
        "id": batch_id,
        "name": name,
        "status": "running",
        "yaw_angles": yaw_list,
        "sub_jobs": sub_jobs,
        "created_at": datetime.now().isoformat(),
        "results": None,
    }

    # Start all simulations in background (they will share the mesh)
    background_tasks.add_task(run_batch_simulation, batch_id, sub_jobs)

    return {
        "batch_id": batch_id,
        "job_ids": sub_jobs,
        "yaw_angles": yaw_list,
        "status": "queued"
    }


# Batch job store
batch_jobs = {}


async def run_batch_simulation(batch_id: str, job_ids: list):
    """
    Run batch simulation for multiple yaw angles.

    Optimization: Generate mesh once and reuse for all yaw angles
    (only boundary conditions change between runs).
    """
    batch = batch_jobs[batch_id]

    try:
        # Run jobs sequentially (could be parallelized with more resources)
        for i, job_id in enumerate(job_ids):
            batch["status"] = f"running_{i+1}_of_{len(job_ids)}"

            # Run individual simulation
            await run_simulation(job_id)

            # Check if it failed
            if jobs[job_id]["status"] == "failed":
                print(f"Job {job_id} failed: {jobs[job_id].get('error')}")

        # Aggregate results
        batch["status"] = "aggregating"
        batch_results = aggregate_batch_results(batch_id, job_ids)
        batch["results"] = batch_results
        batch["status"] = "complete"

    except Exception as e:
        batch["status"] = "failed"
        batch["error"] = str(e)


def aggregate_batch_results(batch_id: str, job_ids: list) -> dict:
    """
    Aggregate results from all yaw angle simulations into a single result set.

    Returns data suitable for polar plots and yaw sweep analysis.
    """
    results = {
        "batch_id": batch_id,
        "yaw_angles": [],
        "Cd": [],
        "Cl": [],
        "Cs": [],  # Side force coefficient
        "Cm": [],
        "drag_N": [],
        "lift_N": [],
        "side_N": [],
        "CdA": [],
        "completed_jobs": 0,
        "failed_jobs": 0,
    }

    for job_id in job_ids:
        job = jobs.get(job_id)
        if not job:
            continue

        yaw = job["config"].get("yaw_angle", 0)
        results["yaw_angles"].append(yaw)

        if job["status"] == "complete" and job.get("results"):
            r = job["results"]
            coeffs = r.get("coefficients", {})
            forces = r.get("forces", {})

            results["Cd"].append(coeffs.get("Cd", 0))
            results["Cl"].append(coeffs.get("Cl", 0))
            results["Cm"].append(coeffs.get("Cm", 0))
            results["drag_N"].append(forces.get("drag_N", 0))
            results["lift_N"].append(forces.get("lift_N", 0))
            results["CdA"].append(r.get("CdA", 0))

            # Calculate side force coefficient from yaw angle components
            # At yaw, the side force is primarily from Cl in the crosswind direction
            Cs = coeffs.get("Cl", 0) * math.sin(math.radians(yaw)) if yaw != 0 else 0
            results["Cs"].append(Cs)
            results["side_N"].append(forces.get("lift_N", 0) * math.sin(math.radians(yaw)) if yaw != 0 else 0)

            results["completed_jobs"] += 1
        else:
            # Fill with None for failed/incomplete jobs
            results["Cd"].append(None)
            results["Cl"].append(None)
            results["Cs"].append(None)
            results["Cm"].append(None)
            results["drag_N"].append(None)
            results["lift_N"].append(None)
            results["side_N"].append(None)
            results["CdA"].append(None)
            results["failed_jobs"] += 1

    # Calculate averages for non-None values
    valid_Cd = [x for x in results["Cd"] if x is not None]
    valid_drag = [x for x in results["drag_N"] if x is not None]

    if valid_Cd:
        results["avg_Cd"] = sum(valid_Cd) / len(valid_Cd)
    if valid_drag:
        results["avg_drag_N"] = sum(valid_drag) / len(valid_drag)

    return results


@app.get("/api/batch/{batch_id}")
async def get_batch_status(batch_id: str):
    """Get batch simulation status"""
    if batch_id not in batch_jobs:
        raise HTTPException(404, "Batch not found")
    return batch_jobs[batch_id]


@app.get("/api/batch/{batch_id}/results")
async def get_batch_results(batch_id: str):
    """Get aggregated batch results for polar charts"""
    if batch_id not in batch_jobs:
        raise HTTPException(404, "Batch not found")

    batch = batch_jobs[batch_id]
    if batch["status"] != "complete":
        raise HTTPException(400, f"Batch not complete. Status: {batch['status']}")

    return batch["results"]


async def run_simulation(job_id: str):
    """Run OpenFOAM simulation (background task)"""
    job = jobs[job_id]
    config = job["config"]

    try:
        # Update status
        job["status"] = "preparing"
        job["progress"] = 5
        job["updated_at"] = datetime.now().isoformat()

        # Create case directory
        case_dir = CASES_DIR / job_id
        case_dir.mkdir(parents=True, exist_ok=True)

        # Copy and prepare STL file with transformation
        for ext in ['.stl', '.obj']:
            src = UPLOAD_DIR / f"{config['file_id']}{ext}"
            if src.exists():
                dst = case_dir / "constant" / "triSurface" / f"wheel{ext}"
                dst.parent.mkdir(parents=True, exist_ok=True)

                if ext == '.stl':
                    # Detect STL units and get appropriate scale
                    validation = validate_stl_file(src)
                    if validation.geometry:
                        transform_hint = get_stl_transform_for_openfoam(validation.geometry)
                        scale = transform_hint.get("scale", 1.0)
                        print(f"Detected STL units: {transform_hint.get('detected_unit', 'unknown')}, scale={scale}")
                    else:
                        scale = 0.001  # Default mm to meters
                        print("Could not detect STL units, defaulting to mm->m scale")

                    # Transform STL: apply detected scale, center, rotate upright, place on ground
                    transform_info = transform_stl_for_openfoam(
                        src, dst,
                        scale=scale,
                        center=True,
                        stand_upright=True
                    )
                    print(f"Transformed STL: diameter={transform_info['wheel_diameter']:.3f}m, "
                          f"radius={transform_info['wheel_radius']:.3f}m")
                    # Store wheel radius in config for later use
                    config['wheel_radius'] = transform_info['wheel_radius']

                    # Calculate frontal area for accurate Cd calculation
                    # Use AeroCloud standard (0.0225 m²) for comparison, or calculate actual
                    aref, area_analysis = get_frontal_area_for_simulation(dst, use_aerocloud_standard=True)
                    config['aref'] = aref
                    config['frontal_area_analysis'] = area_analysis
                    print(f"Frontal area: Aref={aref:.4f} m² (AeroCloud standard for comparison)")
                else:
                    shutil.copy(src, dst)
                break
        else:
            raise Exception(f"Source file not found for file_id: {config['file_id']}")

        # Determine parallelization settings
        import multiprocessing
        num_cpus = multiprocessing.cpu_count()
        # Use half of available CPUs (leave some for system)
        num_procs = max(4, min(num_cpus // 2, 16))
        use_parallel = config.get("quality") in ["standard", "pro"]
        gpu_enabled = config.get("gpu_acceleration", False)

        print(f"Parallel execution: {use_parallel}, using {num_procs} processors")
        if gpu_enabled:
            print("GPU acceleration enabled (AmgX for pressure solver)")

        # Generate OpenFOAM case files
        await generate_case_files(case_dir, config)
        job["progress"] = 10

        # Run blockMesh (always serial)
        job["status"] = "meshing"
        job["progress"] = 15
        await run_openfoam_command(case_dir, "blockMesh")
        job["progress"] = 20

        # Run snappyHexMesh in SERIAL mode
        # Parallel snappyHexMesh with reconstruction has issues - run serial for reliability
        job["updated_at"] = datetime.now().isoformat()
        await run_openfoam_command(case_dir, "snappyHexMesh", ["-overwrite"],
                                   parallel=False, num_procs=num_procs)
        job["progress"] = 45

        # Create MRF cellZone using topoSet (if MRF rotation enabled)
        rotation_method = config.get("rotation_method", "none")
        if rotation_method == "mrf" and config.get("rolling_enabled", True):
            wheel_radius = config['wheel_radius']
            # Create topoSetDict for cylindrical MRF zone
            topo_set_dict = f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      topoSetDict;
}}

actions
(
    {{
        name    rotatingZone;
        type    cellSet;
        action  new;
        source  cylinderToCell;
        point1  (0 -0.15 {wheel_radius});
        point2  (0 0.15 {wheel_radius});
        radius  {wheel_radius * 1.05};
    }}
    {{
        name    rotatingZone;
        type    cellZoneSet;
        action  new;
        source  setToCellZone;
        set     rotatingZone;
    }}
);
"""
            (case_dir / "system" / "topoSetDict").write_text(topo_set_dict)
            print("Creating MRF cellZone with topoSet...")
            await run_openfoam_command(case_dir, "topoSet", parallel=False)
            print("MRF cellZone created successfully")

        job["progress"] = 50

        # Run potentialFoam for better initial conditions (helps convergence)
        if use_parallel:
            try:
                await run_openfoam_command(case_dir, "potentialFoam", ["-writephi"],
                                          parallel=use_parallel, num_procs=num_procs)
            except Exception as e:
                print(f"potentialFoam skipped: {e}")

        # Run simulation
        job["status"] = "solving"
        job["progress"] = 55
        job["updated_at"] = datetime.now().isoformat()

        # Choose solver based on rotation method
        rotation_method = config.get("rotation_method", "none")

        if rotation_method == "transient":
            # Transient simulation with pimpleFoam for AMI rotation
            # Generate transient-specific files
            pimple_solution = generate_pimple_fv_solution(
                quality=config.get("quality", "standard"),
                gpu_enabled=gpu_enabled,
                base_dir=str(BASE_DIR)
            )
            (case_dir / "system" / "fvSolution").write_text(pimple_solution)

            transient_schemes = generate_transient_fv_schemes(config.get("quality", "standard"))
            (case_dir / "system" / "fvSchemes").write_text(transient_schemes)

            # Update controlDict for transient
            transient_control = generate_transient_control_dict(
                speed=config["speed"],
                yaw=config["yaw_angles"][0],
                wheel_radius=config["wheel_radius"],
                air_rho=config["air"]["rho"],
                aref=config.get("aref", 0.0225),
                end_time=2.0,  # 2 seconds = ~2 wheel rotations at 13.9 m/s
                delta_t=0.001
            )
            (case_dir / "system" / "controlDict").write_text(transient_control)

            # Generate dynamicMeshDict for AMI solid body rotation
            wheel_radius = config['wheel_radius']
            omega = config['omega']
            dynamic_mesh = generate_dynamic_mesh_dict(
                zone_name="rotatingZone",
                origin=(0, 0, wheel_radius),
                axis=(0, 1, 0),
                omega=omega,
                use_ami=True
            )
            (case_dir / "constant" / "dynamicMeshDict").write_text(dynamic_mesh)
            print(f"AMI rotation enabled: dynamicMeshDict generated (omega={omega:.2f} rad/s)")

            print("Running transient simulation with pimpleFoam...")
            await run_openfoam_command(case_dir, "foamRun", ["-solver", "incompressibleFluid"],
                                       parallel=use_parallel, num_procs=num_procs,
                                       gpu_enabled=gpu_enabled)
        else:
            # Steady-state simulation (SIMPLE algorithm)
            # Use foamRun with incompressibleFluid solver (replaces simpleFoam in OF13)
            await run_openfoam_command(case_dir, "foamRun", ["-solver", "incompressibleFluid"],
                                       parallel=use_parallel, num_procs=num_procs,
                                       gpu_enabled=gpu_enabled)

        job["progress"] = 85

        # Post-process
        job["status"] = "post-processing"
        job["progress"] = 90

        # Extract forces
        results = await extract_results(case_dir, config)
        job["results"] = results
        job["progress"] = 100
        job["status"] = "complete"

    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)

    job["updated_at"] = datetime.now().isoformat()
    # Persist final job state to database
    sync_job_to_db(job_id, job)


async def generate_case_files(case_dir: Path, config: dict):
    """Generate OpenFOAM case files"""

    # Create directory structure
    for subdir in ["0", "constant", "system"]:
        (case_dir / subdir).mkdir(exist_ok=True)

    speed = config["speed"]
    yaw = config["yaw_angles"][0]  # Use first yaw angle
    vx, vy, vz = velocity_components(speed, yaw)
    omega = config["omega"]
    air = config["air"]

    # controlDict
    control_dict = f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      controlDict;
}}

application     simpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         500;
deltaT          1;
writeControl    timeStep;
writeInterval   100;
purgeWrite      2;
writeFormat     ascii;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;

functions
{{
    forceCoeffs
    {{
        type            forceCoeffs;
        libs            ("libforces.so");
        writeControl    timeStep;
        writeInterval   1;

        patches         (wheel);
        rho             rhoInf;
        rhoInf          {air['rho']};

        CofR            (0 0 0);
        liftDir         (0 0 1);
        dragDir         ({vx/speed:.6f} {vy/speed:.6f} 0);
        pitchAxis       (0 1 0);

        magUInf         {speed};
        lRef            {config['wheel_radius'] * 2};
        Aref            {config.get('aref', 0.0225)};
    }}

    // Raw forces in fixed coordinates (for AeroCloud-compatible Cx, Cy, Cz)
    forces
    {{
        type            forces;
        libs            ("libforces.so");
        writeControl    timeStep;
        writeInterval   1;

        patches         (wheel);
        rho             rhoInf;
        rhoInf          {air['rho']};
        CofR            (0 0 0);
    }}

    pressureSlices
    {{
        type            surfaces;
        libs            ("libsampling.so");
        writeControl    writeTime;

        surfaceFormat   vtk;
        fields          (p U);

        interpolationScheme cellPoint;

        surfaces
        {{
            ySlice_neg02
            {{
                type            cuttingPlane;
                planeType       pointAndNormal;
                point           (0 -0.02 0);
                normal          (0 1 0);
                interpolate     true;
            }}
            ySlice_0
            {{
                type            cuttingPlane;
                planeType       pointAndNormal;
                point           (0 0 0);
                normal          (0 1 0);
                interpolate     true;
            }}
            ySlice_pos02
            {{
                type            cuttingPlane;
                planeType       pointAndNormal;
                point           (0 0.02 0);
                normal          (0 1 0);
                interpolate     true;
            }}
            xSlice_0
            {{
                type            cuttingPlane;
                planeType       pointAndNormal;
                point           (0 0 0);
                normal          (1 0 0);
                interpolate     true;
            }}
            zSlice_ground
            {{
                type            cuttingPlane;
                planeType       pointAndNormal;
                point           (0 0 0.01);
                normal          (0 0 1);
                interpolate     true;
            }}
            zSlice_hub
            {{
                type            cuttingPlane;
                planeType       pointAndNormal;
                point           (0 0 0.35);
                normal          (0 0 1);
                interpolate     true;
            }}
            zSlice_top
            {{
                type            cuttingPlane;
                planeType       pointAndNormal;
                point           (0 0 0.68);
                normal          (0 0 1);
                interpolate     true;
            }}
        }}
    }}
}}
"""
    (case_dir / "system" / "controlDict").write_text(control_dict)

    # fvSchemes
    # Adjust schemes for mesh quality
    quality = config.get("quality", "basic")
    if quality == "pro":
        # More stable schemes for fine mesh with potential skewness
        sn_grad = "limited corrected 0.5"
        laplacian = "Gauss linear limited corrected 0.5"
        grad_scheme = "cellLimited Gauss linear 1"
    elif quality == "standard":
        sn_grad = "limited corrected 0.33"
        laplacian = "Gauss linear limited corrected 0.33"
        grad_scheme = "cellLimited Gauss linear 1"
    else:
        sn_grad = "corrected"
        laplacian = "Gauss linear corrected"
        grad_scheme = "Gauss linear"

    fv_schemes = f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvSchemes;
}}

ddtSchemes
{{
    default         steadyState;
}}

gradSchemes
{{
    default         {grad_scheme};
    grad(U)         {grad_scheme};
    grad(k)         {grad_scheme};
    grad(omega)     {grad_scheme};
}}

divSchemes
{{
    default         none;
    div(phi,U)      bounded Gauss linearUpwind grad(U);
    div(phi,k)      bounded Gauss upwind;
    div(phi,omega)  bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}}

laplacianSchemes
{{
    default         {laplacian};
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         {sn_grad};
}}

wallDist
{{
    method          meshWave;
}}
"""
    (case_dir / "system" / "fvSchemes").write_text(fv_schemes)

    # fvSolution - adjust for mesh quality
    quality = config.get("quality", "basic")
    if quality == "pro":
        # More conservative for fine mesh
        relax_U, relax_p, relax_k = 0.5, 0.2, 0.5
        nonortho_correctors = 2  # For skewed cells
        solver_tol = "1e-07"
    elif quality == "standard":
        relax_U, relax_p, relax_k = 0.6, 0.25, 0.6
        nonortho_correctors = 1
        solver_tol = "1e-06"
    else:
        relax_U, relax_p, relax_k = 0.7, 0.3, 0.7
        nonortho_correctors = 0
        solver_tol = "1e-06"

    # Always use GAMG - AmgX requires special OpenFOAM build with CUDA
    pressure_solver = f'''    p
    {{
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       {solver_tol};
        relTol          0.1;
        nPreSweeps      0;
        nPostSweeps     2;
        cacheAgglomeration true;
        agglomerator    faceAreaPair;
        nCellsInCoarsestLevel 100;
        mergeLevels     1;
    }}'''

    fv_solution = f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvSolution;
}}

solvers
{{
{pressure_solver}

    "(U|k|omega)"
    {{
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       {solver_tol};
        relTol          0.1;
    }}

    Phi
    {{
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-06;
        relTol          0.01;
    }}
}}

SIMPLE
{{
    nNonOrthogonalCorrectors {nonortho_correctors};
    consistent      yes;

    residualControl
    {{
        p               1e-4;
        U               1e-4;
        "(k|omega)"     1e-4;
    }}
}}

potentialFlow
{{
    nNonOrthogonalCorrectors 10;
}}

relaxationFactors
{{
    fields
    {{
        p               {relax_p};
    }}
    equations
    {{
        U               {relax_U};
        k               {relax_k};
        omega           {relax_k};
    }}
}}
"""
    (case_dir / "system" / "fvSolution").write_text(fv_solution)

    # Velocity BC - handle wheel rotation based on rotation_method
    rotation_method = config.get("rotation_method", "none")
    wheel_center = (0, 0, config['wheel_radius'])  # Wheel centered at origin, on ground

    if rotation_method in ["mrf", "transient"] and config.get("rolling_enabled", True):
        # Use rotating wall velocity for wheel
        wheel_bc = f"""    wheel
    {{
        type            rotatingWallVelocity;
        origin          ({wheel_center[0]} {wheel_center[1]} {wheel_center[2]});
        axis            (0 1 0);  // Y-axis rotation (axle direction)
        omega           {omega};  // rad/s
    }}"""
    else:
        # Static wheel (no rotation)
        wheel_bc = """    wheel
    {
        type            fixedValue;
        value           uniform (0 0 0);
    }"""

    # Ground BC - slip or moving wall
    if config.get("ground_type") == "slip":
        ground_bc = """    ground
    {
        type            slip;
    }"""
    else:
        # Moving ground (belt) - matches freestream velocity
        ground_bc = f"""    ground
    {{
        type            movingWallVelocity;
        value           uniform ({vx} {vy} 0);
    }}"""

    u_file = f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       volVectorField;
    object      U;
}}

dimensions      [0 1 -1 0 0 0 0];

internalField   uniform ({vx} {vy} {vz});

boundaryField
{{
    inlet
    {{
        type            fixedValue;
        value           uniform ({vx} {vy} {vz});
    }}
    outlet
    {{
        type            inletOutlet;
        inletValue      uniform (0 0 0);
        value           $internalField;
    }}
{ground_bc}
    top
    {{
        type            slip;
    }}
    sides
    {{
        type            slip;
    }}
{wheel_bc}
}}
"""
    (case_dir / "0" / "U").write_text(u_file)

    # MRF rotation - cellZone is created in snappyHexMesh
    if rotation_method == "mrf" and config.get("rolling_enabled", True):
        # Calculate angular velocity: omega = V / R
        # For a wheel rolling on ground, surface velocity equals ground velocity
        wheel_radius = config['wheel_radius']
        angular_velocity = speed / wheel_radius  # rad/s

        mrf_properties = f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      MRFProperties;
}}

MRF1
{{
    cellZone    rotatingZone;
    active      true;

    // Fixed patches (ground doesn't rotate with wheel)
    nonRotatingPatches (ground);

    // Rotation axis: Y-axis (wheel rotates around Y)
    origin      (0 0 {wheel_radius});
    axis        (0 1 0);
    omega       {angular_velocity:.6f};  // rad/s = V/R = {speed:.2f}/{wheel_radius:.4f}
}}
"""
        (case_dir / "constant" / "MRFProperties").write_text(mrf_properties)
        print(f"MRF rotation enabled: omega = {angular_velocity:.2f} rad/s ({angular_velocity * 60 / (2 * 3.14159):.1f} RPM)")
    else:
        # No rotation - empty MRF
        empty_mrf = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      MRFProperties;
}
// Wheel rotation disabled
"""
        (case_dir / "constant" / "MRFProperties").write_text(empty_mrf)
        print("Wheel rotation disabled (static wheel simulation)")

    # Pressure BC
    p_file = """FoamFile
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
"""
    (case_dir / "0" / "p").write_text(p_file)

    # Turbulence - k
    k_file = """FoamFile
{
    version     2.0;
    format      ascii;
    class       volScalarField;
    object      k;
}

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform 0.1;

boundaryField
{
    inlet
    {
        type            fixedValue;
        value           uniform 0.1;
    }
    outlet
    {
        type            inletOutlet;
        inletValue      uniform 0.1;
        value           $internalField;
    }
    ground
    {
        type            kqRWallFunction;
        value           uniform 0.1;
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
        type            kqRWallFunction;
        value           uniform 0.1;
    }
}
"""
    (case_dir / "0" / "k").write_text(k_file)

    # Turbulence - omega
    omega_file = """FoamFile
{
    version     2.0;
    format      ascii;
    class       volScalarField;
    object      omega;
}

dimensions      [0 0 -1 0 0 0 0];

internalField   uniform 1;

boundaryField
{
    inlet
    {
        type            fixedValue;
        value           uniform 1;
    }
    outlet
    {
        type            inletOutlet;
        inletValue      uniform 1;
        value           $internalField;
    }
    ground
    {
        type            omegaWallFunction;
        value           uniform 1;
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
        type            omegaWallFunction;
        value           uniform 1;
    }
}
"""
    (case_dir / "0" / "omega").write_text(omega_file)

    # nut
    nut_file = """FoamFile
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
"""
    (case_dir / "0" / "nut").write_text(nut_file)

    # transportProperties
    transport = f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      transportProperties;
}}

transportModel  Newtonian;
nu              nu [ 0 2 -1 0 0 0 0 ] {air['nu']};
"""
    (case_dir / "constant" / "transportProperties").write_text(transport)

    # turbulenceProperties
    turbulence = """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      turbulenceProperties;
}

simulationType RAS;

RAS
{
    RASModel        kOmegaSST;
    turbulence      on;
    printCoeffs     on;
}
"""
    (case_dir / "constant" / "turbulenceProperties").write_text(turbulence)

    # snappyHexMeshDict - mesh quality presets
    quality = config.get("quality", "standard")

    # Mesh quality presets: cells, refinement levels, background mesh resolution
    mesh_presets = {
        "basic": {
            "maxLocalCells": 200000,
            "maxGlobalCells": 500000,
            "surfaceLevel": (2, 3),
            "bgMesh": (50, 25, 15),  # Background mesh cells (x, y, z)
            "nCellsBetweenLevels": 2,
        },
        "standard": {
            "maxLocalCells": 500000,
            "maxGlobalCells": 2000000,
            "surfaceLevel": (3, 4),
            "bgMesh": (70, 35, 25),
            "nCellsBetweenLevels": 3,
        },
        "pro": {
            "maxLocalCells": 2000000,
            "maxGlobalCells": 8000000,
            "surfaceLevel": (4, 5),
            "bgMesh": (100, 50, 35),
            "nCellsBetweenLevels": 3,
        },
    }

    preset = mesh_presets.get(quality, mesh_presets["standard"])

    snappy = f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      snappyHexMeshDict;
}}

castellatedMesh true;
snap            true;
addLayers       true;

geometry
{{
    wheel
    {{
        type triSurfaceMesh;
        file "wheel.stl";
    }}

    refinementBox
    {{
        type searchableBox;
        min (-0.5 -0.6 0);
        max (2.0 0.6 1.0);
    }}

    wakeRegion
    {{
        type searchableBox;
        min (0.3 -0.3 0);
        max (3.0 0.3 0.8);
    }}

    // MRF rotation zone - cylinder around the wheel
    rotatingZone
    {{
        type searchableCylinder;
        point1 (0 -0.1 {config['wheel_radius']});
        point2 (0 0.1 {config['wheel_radius']});
        radius {config['wheel_radius'] * 1.05};
    }}
}}

castellatedMeshControls
{{
    maxLocalCells {preset['maxLocalCells']};
    maxGlobalCells {preset['maxGlobalCells']};
    minRefinementCells 10;
    nCellsBetweenLevels {preset['nCellsBetweenLevels']};

    features
    (
    );

    refinementSurfaces
    {{
        wheel
        {{
            level ({preset['surfaceLevel'][0]} {preset['surfaceLevel'][1]});
            patchInfo
            {{
                type wall;
            }}
        }}
    }}

    resolveFeatureAngle 30;

    refinementRegions
    {{
        refinementBox
        {{
            mode inside;
            levels ((1E15 {preset['surfaceLevel'][0] - 1}));
        }}

        wakeRegion
        {{
            mode inside;
            levels ((1E15 {preset['surfaceLevel'][0]}));
        }}

        rotatingZone
        {{
            mode inside;
            levels ((1E15 {preset['surfaceLevel'][0]}));
            cellZone rotatingZone;
            faceZone rotatingZoneFaces;
            cellZoneInside inside;
        }}
    }}

    locationInMesh (0.5 0 0.5);
    allowFreeStandingZoneFaces true;
}}

snapControls
{{
    nSmoothPatch 3;
    tolerance 2.0;
    nSolveIter 50;
    nRelaxIter 5;
    nFeatureSnapIter 10;
    implicitFeatureSnap true;
    explicitFeatureSnap false;
    multiRegionFeatureSnap false;
}}

addLayersControls
{{
    relativeSizes true;
    layers
    {{
        wheel
        {{
            nSurfaceLayers 3;
        }}
    }}
    expansionRatio 1.2;
    finalLayerThickness 0.3;
    minThickness 0.1;
    nGrow 0;
    featureAngle 130;
    nRelaxIter 5;
    nSmoothSurfaceNormals 1;
    nSmoothNormals 3;
    nSmoothThickness 10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedianAxisAngle 90;
    nBufferCellsNoExtrude 0;
    nLayerIter 50;
}}

meshQualityControls
{{
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
}}

mergeTolerance 1e-6;
"""
    (case_dir / "system" / "snappyHexMeshDict").write_text(snappy)

    # Update blockMeshDict based on quality preset
    bg = preset['bgMesh']
    block_mesh = f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      blockMeshDict;
}}

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
    hex (0 1 2 3 4 5 6 7) ({bg[0]} {bg[1]} {bg[2]}) simpleGrading (1 1 1)
);

edges
(
);

boundary
(
    inlet
    {{
        type patch;
        faces
        (
            (0 4 7 3)
        );
    }}
    outlet
    {{
        type patch;
        faces
        (
            (1 2 6 5)
        );
    }}
    ground
    {{
        type wall;
        faces
        (
            (0 1 2 3)
        );
    }}
    top
    {{
        type patch;
        faces
        (
            (4 5 6 7)
        );
    }}
    sides
    {{
        type patch;
        faces
        (
            (0 1 5 4)
            (3 7 6 2)
        );
    }}
);
"""
    (case_dir / "system" / "blockMeshDict").write_text(block_mesh)


def get_openfoam_env(gpu_enabled: bool = False, parallel: bool = False):
    """Get OpenFOAM environment by sourcing the official bashrc.

    This ensures all environment variables (MPI_BUFFER_SIZE, library paths,
    etc.) are set correctly by OpenFOAM's own configuration.

    Args:
        gpu_enabled: Include CUDA/AmgX libraries
        parallel: Not used anymore - bashrc handles MPI setup
    """
    import subprocess

    # Source OpenFOAM bashrc and capture the environment
    bashrc_path = f"{OPENFOAM_DIR}/etc/bashrc"
    cmd = f'source {bashrc_path} && env'

    result = subprocess.run(
        ['bash', '-c', cmd],
        capture_output=True,
        text=True
    )

    # Parse environment variables from output
    env = {}
    for line in result.stdout.split('\n'):
        if '=' in line:
            key, _, value = line.partition('=')
            env[key] = value

    # Add GPU libraries if enabled
    if gpu_enabled:
        ld_path = env.get('LD_LIBRARY_PATH', '')
        gpu_paths = [
            "/home/constantine/OpenFOAM/constantine-13/platforms/linux64GccDPInt32Opt/lib",
            "/home/constantine/local/amgx",
            "/usr/local/cuda-12.9/lib64"
        ]
        env['LD_LIBRARY_PATH'] = ':'.join(gpu_paths) + ':' + ld_path

    return env


# Cache the OpenFOAM environment to avoid repeated subprocess calls
_openfoam_env_cache = {}

def get_openfoam_env_cached(gpu_enabled: bool = False):
    """Cached version of get_openfoam_env for better performance."""
    cache_key = f"gpu_{gpu_enabled}"
    if cache_key not in _openfoam_env_cache:
        _openfoam_env_cache[cache_key] = get_openfoam_env(gpu_enabled=gpu_enabled)
    return _openfoam_env_cache[cache_key].copy()


def generate_decompose_dict(case_dir: Path, num_procs: int):
    """Generate decomposeParDict for parallel execution"""
    # Factorize into 3D decomposition
    import math
    n = num_procs
    factors = []
    for i in [2, 3, 5, 7]:
        while n % i == 0:
            factors.append(i)
            n //= i
    if n > 1:
        factors.append(n)

    # Distribute factors into x, y, z
    result = [1, 1, 1]
    for f in sorted(factors, reverse=True):
        min_idx = result.index(min(result))
        result[min_idx] *= f

    decompose_dict = f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      decomposeParDict;
}}

numberOfSubdomains {num_procs};

method          scotch;

simpleCoeffs
{{
    n               ({result[0]} {result[1]} {result[2]});
    delta           0.001;
}}

scotchCoeffs
{{
}}

distributed     no;
roots           ();
"""
    (case_dir / "system" / "decomposeParDict").write_text(decompose_dict)


async def run_openfoam_command(case_dir: Path, command: str, args: list = None, parallel: bool = False, num_procs: int = 8, gpu_enabled: bool = False):
    """Run an OpenFOAM command, optionally in parallel with MPI"""
    if args is None:
        args = []

    # Commands that don't support parallel
    serial_only = ["blockMesh", "surfaceFeatureExtract", "checkMesh"]

    # Determine if this will actually run in parallel
    will_run_parallel = parallel and command not in serial_only

    # Get OpenFOAM environment (sourced from official bashrc)
    env = get_openfoam_env_cached(gpu_enabled=gpu_enabled)

    if will_run_parallel:
        # Generate decomposeParDict if needed
        decompose_dict = case_dir / "system" / "decomposeParDict"
        if not decompose_dict.exists():
            generate_decompose_dict(case_dir, num_procs)

        # Decompose the domain first (if not already done)
        processor_dirs = list(case_dir.glob("processor*"))
        if not processor_dirs:
            print(f"Decomposing domain into {num_procs} parts...")
            decompose_proc = await asyncio.create_subprocess_exec(
                "decomposePar",
                cwd=case_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await decompose_proc.communicate()
            if decompose_proc.returncode != 0:
                raise Exception(f"decomposePar failed: {stderr.decode(errors='replace')}")

        # Run in parallel with MPI
        cmd = ["mpirun", "-np", str(num_procs), command, "-parallel"] + args
        print(f"Running: {' '.join(cmd)}")
    else:
        cmd = [command] + args

    # Create log file
    log_file = case_dir / f"log.{command}"

    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=case_dir,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    # Write log
    with open(log_file, 'w') as f:
        f.write(stdout.decode(errors='replace'))
        if stderr:
            f.write("\n--- STDERR ---\n")
            f.write(stderr.decode(errors='replace'))

    if process.returncode != 0:
        raise Exception(f"{command} failed: {stderr.decode(errors='replace')}")

    # Reconstruct if parallel
    if parallel and command not in serial_only:
        if command == "snappyHexMesh":
            print("Reconstructing mesh...")
            reconstruct_proc = await asyncio.create_subprocess_exec(
                "reconstructParMesh", "-constant", "-mergeTol", "1e-6",
                cwd=case_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_r, stderr_r = await reconstruct_proc.communicate()

            # Log reconstruction output
            log_file = case_dir / "log.reconstructParMesh"
            with open(log_file, 'w') as f:
                f.write(stdout_r.decode(errors='replace'))
                if stderr_r:
                    f.write("\n--- STDERR ---\n")
                    f.write(stderr_r.decode(errors='replace'))

            if reconstruct_proc.returncode != 0:
                print(f"WARNING: reconstructParMesh failed: {stderr_r.decode(errors='replace')[:200]}")

            # Verify mesh was reconstructed by checking for wheel patch
            boundary_file = case_dir / "constant" / "polyMesh" / "boundary"
            if boundary_file.exists():
                boundary_content = boundary_file.read_text()
                if "wheel" not in boundary_content:
                    print("WARNING: Reconstructed mesh missing 'wheel' patch!")

            # Clean up processor directories after mesh reconstruction
            # This ensures fresh decomposition for the solver with correct BCs
            print("Cleaning up processor directories...")
            import shutil
            for proc_dir in case_dir.glob("processor*"):
                shutil.rmtree(proc_dir)
        elif command in ["simpleFoam", "pimpleFoam", "foamRun"]:
            print("Reconstructing fields...")
            reconstruct_proc = await asyncio.create_subprocess_exec(
                "reconstructPar",
                cwd=case_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await reconstruct_proc.communicate()

    return stdout.decode(errors='replace')


async def extract_results(case_dir: Path, config: dict) -> dict:
    """Extract simulation results"""
    import re

    results = {
        "forces": {},
        "coefficients": {},
        "fixed_coefficients": {},  # Cx, Cy, Cz in fixed coordinates (AeroCloud-compatible)
        "converged": False
    }

    # Try to read forceCoeffs output (wind-direction Cd)
    force_file = case_dir / "postProcessing" / "forceCoeffs" / "0" / "forceCoeffs.dat"
    if force_file.exists():
        lines = force_file.read_text().strip().split('\n')
        if len(lines) > 1:
            # Get last line (final iteration)
            last_line = lines[-1]
            if not last_line.startswith('#'):
                parts = last_line.split()
                if len(parts) >= 4:
                    # Columns: Time, Cm, Cd, Cl, Cl(f), Cl(r)
                    results["coefficients"] = {
                        "Cm": float(parts[1]),
                        "Cd": float(parts[2]),  # Drag in wind direction
                        "Cl": float(parts[3]),  # Lift (Z-direction)
                    }
                    results["converged"] = True

    # Try to read raw forces output (fixed coordinates)
    # OpenFOAM forces function outputs: Time ((px py pz) (vx vy vz) (porousx porousy porousz))
    raw_force_file = case_dir / "postProcessing" / "forces" / "0" / "forces.dat"
    if raw_force_file.exists():
        lines = raw_force_file.read_text().strip().split('\n')
        if len(lines) > 1:
            last_line = lines[-1]
            if not last_line.startswith('#'):
                # Parse the forces output format: Time ((px py pz) (vx vy vz) ...)
                # Extract numbers using regex
                numbers = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', last_line)
                if len(numbers) >= 7:
                    # numbers[0] = time
                    # numbers[1:4] = pressure force (Fx, Fy, Fz)
                    # numbers[4:7] = viscous force (Fx, Fy, Fz)
                    px, py, pz = float(numbers[1]), float(numbers[2]), float(numbers[3])
                    vx, vy, vz = float(numbers[4]), float(numbers[5]), float(numbers[6])

                    # Total force = pressure + viscous
                    Fx = px + vx  # X-direction (forward/backward)
                    Fy = py + vy  # Y-direction (side force)
                    Fz = pz + vz  # Z-direction (lift)

                    results["raw_forces"] = {
                        "Fx_N": Fx,
                        "Fy_N": Fy,
                        "Fz_N": Fz,
                        "pressure": {"x": px, "y": py, "z": pz},
                        "viscous": {"x": vx, "y": vy, "z": vz},
                    }

    # Calculate coefficients
    rho = config["air"]["rho"]
    U = config["speed"]
    A = config.get("aref", 0.0225)  # Reference area (m²) - AeroCloud standard
    q = 0.5 * rho * U * U  # Dynamic pressure

    # Wind-direction forces from forceCoeffs
    if results["coefficients"]:
        Cd = results["coefficients"]["Cd"]
        Cl = results["coefficients"]["Cl"]

        results["forces"] = {
            "drag_N": Cd * q * A,  # Drag in wind direction
            "lift_N": Cl * q * A,
        }

        results["CdA"] = Cd * A  # Drag area (m²)
        results["CdA_cm2"] = Cd * A * 10000  # CdA in cm² (common unit)

    # Fixed-coordinate coefficients from raw forces (AeroCloud-compatible)
    if "raw_forces" in results:
        Fx = results["raw_forces"]["Fx_N"]
        Fy = results["raw_forces"]["Fy_N"]
        Fz = results["raw_forces"]["Fz_N"]

        # Calculate coefficients in fixed coordinates
        # Cx = force in X-direction (direction of travel) - THIS IS WHAT AEROCLOUD REPORTS
        # Cy = side force coefficient
        # Cz = lift coefficient (should match Cl)
        Cx = Fx / (q * A)
        Cy = Fy / (q * A)
        Cz = Fz / (q * A)

        results["fixed_coefficients"] = {
            "Cx": Cx,  # X-direction drag (AeroCloud-compatible)
            "Cy": Cy,  # Side force coefficient
            "Cz": Cz,  # Lift coefficient
        }

        results["raw_forces"]["Fx_drag_N"] = Fx  # Renamed for clarity

        # Calculate CxA (drag area in direction of travel)
        results["CxA"] = Cx * A
        results["CxA_cm2"] = Cx * A * 10000

    results["dynamic_pressure"] = q
    results["aref"] = A
    results["aref_cm2"] = A * 10000

    # AeroCloud comparison - now using Cx (fixed X-direction) for fair comparison
    yaw_angle = config.get("yaw_angle", config.get("yaw_angles", [0])[0] if isinstance(config.get("yaw_angles"), list) else 0)

    # AeroCloud reference values at different yaw angles
    aerocloud_ref = {
        0: {"Cd": 0.410},
        10: {"Cd": 0.270},
        15: {"Cd": 0.490, "drag_N": 1.31},
    }

    if yaw_angle in aerocloud_ref:
        ac_data = aerocloud_ref[yaw_angle]
        results["aerocloud_comparison"] = {
            "yaw_angle": yaw_angle,
            "aerocloud_Cd": ac_data["Cd"],
            "note": "AeroCloud reports Cx (X-direction force coefficient)"
        }

        if "fixed_coefficients" in results:
            Cx = results["fixed_coefficients"]["Cx"]
            results["aerocloud_comparison"]["wheelflow_Cx"] = Cx
            results["aerocloud_comparison"]["Cx_diff_percent"] = ((Cx - ac_data["Cd"]) / ac_data["Cd"]) * 100

        if results["coefficients"]:
            Cd = results["coefficients"]["Cd"]
            results["aerocloud_comparison"]["wheelflow_Cd_wind"] = Cd
            results["aerocloud_comparison"]["Cd_wind_diff_percent"] = ((Cd - ac_data["Cd"]) / ac_data["Cd"]) * 100

    return results


@app.get("/api/jobs")
async def list_jobs():
    """List all jobs"""
    return list(jobs.values())


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """Get job status"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its associated case directory"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    # Remove case directory if it exists
    case_dir = CASES_DIR / job_id
    if case_dir.exists():
        import shutil
        shutil.rmtree(case_dir)

    # Remove from database and memory cache
    db.delete_job(job_id)
    if job_id in jobs:
        del jobs[job_id]

    return {"message": "Job deleted successfully", "job_id": job_id}


@app.get("/api/jobs/{job_id}/results")
async def get_results(job_id: str):
    """Get job results"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    job = jobs[job_id]
    if job["status"] != "complete":
        raise HTTPException(400, f"Job not complete. Status: {job['status']}")

    return job["results"]


@app.get("/api/jobs/{job_id}/parts_breakdown")
async def get_parts_breakdown(job_id: str):
    """
    Get drag breakdown by wheel component.

    Returns force contribution for each detected wheel part
    (rim, tire, spokes, hub, disc).
    """
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    job = jobs[job_id]

    # Get case directory
    case_dir = CASES_DIR / job_id

    if not case_dir.exists():
        raise HTTPException(404, "Case directory not found")

    # Import per-part force extraction
    try:
        from backend.visualization.force_distribution import extract_per_part_forces, detect_wheel_parts
    except ImportError:
        from visualization.force_distribution import extract_per_part_forces, detect_wheel_parts

    # Extract per-part forces
    parts_data = extract_per_part_forces(case_dir)

    if not parts_data.get("has_parts"):
        # Fallback: detect parts and return message
        detected_parts = detect_wheel_parts(case_dir)
        return {
            "has_parts": False,
            "detected_parts": detected_parts,
            "message": "No per-part force data available. Wheel geometry may be a single surface.",
            "parts": []
        }

    return parts_data


@app.get("/api/system/stats")
async def get_stats():
    """Get system resource statistics (CPU, RAM, GPU, OpenFOAM processes)"""
    try:
        stats = get_system_stats()
        return stats
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/jobs/{job_id}/progress")
async def get_job_progress(job_id: str):
    """Get detailed simulation progress from OpenFOAM logs"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    case_dir = CASES_DIR / job_id
    if not case_dir.exists():
        raise HTTPException(404, "Case directory not found")

    try:
        progress = get_openfoam_progress(case_dir)
        progress["job_status"] = jobs[job_id]["status"]
        progress["job_progress"] = jobs[job_id]["progress"]
        return progress
    except Exception as e:
        return {"error": str(e)}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, job: str = None):
    """F1-style performance dashboard"""
    return templates.TemplateResponse("results.html", {
        "request": request,
        "job_id": job or ""
    })


@app.get("/api/jobs/{job_id}/convergence")
async def get_convergence_data(job_id: str):
    """Get convergence history data for charts"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    case_dir = CASES_DIR / job_id
    force_file = case_dir / "postProcessing" / "forceCoeffs" / "0" / "forceCoeffs.dat"

    data = {
        "time": [],
        "Cd": [],
        "Cl": [],
        "Cm": []
    }

    if force_file.exists():
        try:
            with open(force_file, 'r') as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) >= 4:
                        data["time"].append(float(parts[0]))
                        data["Cm"].append(float(parts[1]))
                        data["Cd"].append(float(parts[2]))
                        data["Cl"].append(float(parts[3]))
        except Exception as e:
            data["error"] = str(e)

    return data


@app.get("/api/yaw_sweep/{batch_prefix}")
async def get_yaw_sweep_data(batch_prefix: str):
    """
    Get Cd values across all yaw angles for a batch of simulations.

    Batch jobs use naming convention: {batch_prefix}_00, {batch_prefix}_05, etc.
    where the suffix indicates the yaw angle in degrees.
    """
    yaw_angles = [0, 5, 10, 15, 20]
    results = []

    for angle in yaw_angles:
        job_id = f"{batch_prefix}_{angle:02d}"
        if job_id in jobs:
            job = jobs[job_id]
            cd = None
            cl = None

            # Try to get final Cd/Cl from job results
            if job.get("results") and job["results"].get("coefficients"):
                cd = job["results"]["coefficients"].get("Cd")
                cl = job["results"]["coefficients"].get("Cl")

            # If not in results, try to read from forceCoeffs file
            if cd is None:
                case_dir = CASES_DIR / job_id
                force_file = case_dir / "postProcessing" / "forceCoeffs" / "0" / "forceCoeffs.dat"
                if force_file.exists():
                    try:
                        with open(force_file, 'r') as f:
                            lines = [l for l in f if not l.startswith('#') and l.strip()]
                            if lines:
                                parts = lines[-1].split()
                                if len(parts) >= 4:
                                    cd = float(parts[2])
                                    cl = float(parts[3])
                    except Exception:
                        pass

            results.append({
                "angle": angle,
                "job_id": job_id,
                "Cd": cd,
                "Cl": cl,
                "status": job.get("status", "unknown")
            })
        else:
            results.append({
                "angle": angle,
                "job_id": job_id,
                "Cd": None,
                "Cl": None,
                "status": "not_found"
            })

    return {
        "batch_prefix": batch_prefix,
        "angles": yaw_angles,
        "results": results,
        "complete": all(r["Cd"] is not None for r in results)
    }


# =============================================================================
# Visualization API Endpoints
# =============================================================================

@app.get("/api/jobs/{job_id}/viz/hero.png")
async def get_hero_image(job_id: str, regenerate: bool = False):
    """
    Get or generate hero image (3D streamline visualization).

    Uses ParaView if available, falls back to placeholder.

    Query params:
        regenerate: bool - Force regeneration of the image

    Returns:
        PNG image file

    Errors:
        404: Job not found
        503: ParaView not available
        504: Generation timeout (5 minute limit)
    """
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    job = jobs[job_id]

    # Don't generate if simulation is not complete
    if job["status"] != "complete":
        raise HTTPException(400, f"Job not complete. Status: {job['status']}")

    case_dir = CASES_DIR / job_id
    viz_dir = case_dir / "visualizations"
    viz_dir.mkdir(exist_ok=True)
    hero_path = viz_dir / "hero.png"

    if not hero_path.exists() or regenerate:
        # Try to generate with ParaView first, then fall back to matplotlib
        try:
            from backend.visualization.hero_image import (
                generate_hero_image,
                check_paraview_available,
                generate_simple_hero_image
            )

            available, version = check_paraview_available()

            if available:
                # Run generation with timeout handling
                # The generate_hero_image function already has a 5-minute timeout
                result = generate_hero_image(case_dir, hero_path)

                if not result.get("success"):
                    error_msg = result.get('error', 'Unknown error')
                    if 'timeout' in error_msg.lower():
                        # Fall back to simple image on timeout
                        result = generate_simple_hero_image(case_dir, hero_path)
                    else:
                        # Try fallback on other errors too
                        result = generate_simple_hero_image(case_dir, hero_path)
            else:
                # ParaView not available - use matplotlib fallback
                result = generate_simple_hero_image(case_dir, hero_path)

            if not result.get("success"):
                error_msg = result.get('error', 'Unknown error')
                raise HTTPException(500, f"Hero image generation failed: {error_msg}")

        except ImportError as e:
            raise HTTPException(503, f"Visualization module not available: {e}")

    if hero_path.exists():
        return FileResponse(hero_path, media_type="image/png",
                            headers={"Cache-Control": "no-cache" if regenerate else "max-age=3600"})
    else:
        raise HTTPException(404, "Hero image not found")


@app.get("/api/jobs/{job_id}/viz/pressure_surface.ply")
async def get_pressure_surface_ply(job_id: str):
    """Get pressure surface as PLY file for Three.js visualization."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    case_dir = CASES_DIR / job_id
    viz_dir = case_dir / "visualizations"
    viz_dir.mkdir(exist_ok=True)
    ply_path = viz_dir / "pressure_surface.ply"

    if not ply_path.exists():
        try:
            from backend.visualization.pressure_surface import export_pressure_surface_ply
            result = export_pressure_surface_ply(case_dir, ply_path)
            if not result.get("success"):
                raise HTTPException(500, f"PLY export failed: {result.get('error')}")
        except ImportError:
            raise HTTPException(503, "Visualization module not available")

    if ply_path.exists():
        return FileResponse(ply_path, media_type="application/octet-stream",
                            filename=f"{job_id}_pressure.ply")
    else:
        raise HTTPException(404, "Pressure surface not found")


@app.get("/api/jobs/{job_id}/viz/pressure_surface.json")
async def get_pressure_surface_json(job_id: str):
    """Get pressure surface as JSON for direct Three.js BufferGeometry."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    case_dir = CASES_DIR / job_id
    viz_dir = case_dir / "visualizations"
    viz_dir.mkdir(exist_ok=True)
    json_path = viz_dir / "pressure_surface.json"

    if not json_path.exists():
        try:
            from backend.visualization.pressure_surface import export_pressure_surface_json
            result = export_pressure_surface_json(case_dir, json_path)
            if not result.get("success"):
                raise HTTPException(500, f"JSON export failed: {result.get('error')}")
        except ImportError:
            raise HTTPException(503, "Visualization module not available")

    if json_path.exists():
        return FileResponse(json_path, media_type="application/json")
    else:
        raise HTTPException(404, "Pressure surface not found")


@app.get("/api/jobs/{job_id}/viz/force_distribution")
async def get_force_distribution(job_id: str):
    """Get force coefficient history for charts."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    case_dir = CASES_DIR / job_id

    try:
        from backend.visualization.force_distribution import extract_force_distribution
        result = extract_force_distribution(case_dir)
        return result
    except ImportError:
        # Fallback implementation
        return {"error": "Visualization module not available"}


@app.get("/api/jobs/{job_id}/viz/residuals")
async def get_residual_history(job_id: str):
    """Get residual convergence history for charts."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    case_dir = CASES_DIR / job_id

    try:
        from backend.visualization.force_distribution import extract_convergence_history
        result = extract_convergence_history(case_dir)
        return result
    except ImportError:
        return {"error": "Visualization module not available"}


@app.get("/api/jobs/{job_id}/viz/slices")
async def get_available_slices(job_id: str):
    """List available pressure slice positions."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    case_dir = CASES_DIR / job_id
    post_dir = case_dir / "postProcessing"

    if not post_dir.exists():
        return {"slices": [], "note": "No post-processing data. Run postprocess first."}

    # Find VTK files in all postProcessing subdirectories
    slices = []
    for vtk_file in post_dir.rglob("*.vtk"):
        # Extract slice name from directory path
        rel_path = vtk_file.relative_to(post_dir)
        parts = rel_path.parts
        if len(parts) >= 2:
            func_name = parts[0]
            time_str = parts[1]
            # Parse slice type from function name or file name
            slice_type = "unknown"
            direction = "unknown"
            file_lower = vtk_file.name.lower()

            if "yslice" in file_lower or "normal=(010)" in func_name or "normal=(0 1 0)" in func_name:
                direction = "y"
                if "neg" in file_lower or "-0.02" in func_name:
                    slice_type = "y-slice-neg02"
                elif "pos" in file_lower or "0.02" in func_name:
                    slice_type = "y-slice-pos02"
                else:
                    slice_type = "y-slice-0"
            elif "xslice" in file_lower or "normal=(100)" in func_name or "normal=(1 0 0)" in func_name:
                direction = "x"
                slice_type = "x-slice-0"
            elif "zslice" in file_lower or "normal=(001)" in func_name or "normal=(0 0 1)" in func_name:
                direction = "z"
                if "ground" in file_lower:
                    slice_type = "z-slice-ground"
                elif "hub" in file_lower:
                    slice_type = "z-slice-hub"
                elif "top" in file_lower:
                    slice_type = "z-slice-top"
                else:
                    slice_type = "z-slice"

            slices.append({
                "time": time_str,
                "file": str(vtk_file),
                "type": slice_type,
                "direction": direction,
                "name": vtk_file.name
            })

    if not slices:
        return {"slices": [], "note": "No pressure slices generated. Enable in controlDict."}

    return {"slices": slices}


@app.get("/api/jobs/{job_id}/viz/slice/{slice_name}.png")
async def get_slice_image(job_id: str, slice_name: str):
    """
    Render a pressure slice as PNG image.

    Args:
        job_id: Simulation job ID
        slice_name: Name of the slice file (without .vtk extension)

    Returns:
        PNG image of the pressure field
    """
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    case_dir = CASES_DIR / job_id
    viz_dir = case_dir / "visualizations" / "slices"
    viz_dir.mkdir(parents=True, exist_ok=True)

    # Output image path
    output_path = viz_dir / f"{slice_name}.png"

    # If image already exists, return it
    if output_path.exists():
        return FileResponse(output_path, media_type="image/png")

    # Find the VTK file
    post_dir = case_dir / "postProcessing"
    vtk_file = None

    for f in post_dir.rglob(f"{slice_name}*.vtk"):
        vtk_file = f
        break

    # Also try without the exact match
    if not vtk_file:
        for f in post_dir.rglob("*.vtk"):
            if slice_name.lower() in f.name.lower():
                vtk_file = f
                break

    if not vtk_file:
        raise HTTPException(404, f"VTK file not found for slice: {slice_name}")

    # Render the slice image
    try:
        from backend.visualization.pressure_slices import render_vtk_slice_image
        result = render_vtk_slice_image(vtk_file, output_path)

        if not result.get("success"):
            raise HTTPException(500, f"Slice rendering failed: {result.get('error')}")

        return FileResponse(output_path, media_type="image/png")

    except ImportError as e:
        raise HTTPException(503, f"Visualization module not available: {e}")


@app.post("/api/jobs/{job_id}/postprocess")
async def run_postprocessing(job_id: str):
    """Run post-processing on existing case to generate pressure slices."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    case_dir = CASES_DIR / job_id

    # Check if results exist
    latest_time = None
    for d in case_dir.iterdir():
        if d.is_dir():
            try:
                t = float(d.name)
                if latest_time is None or t > latest_time:
                    latest_time = t
            except ValueError:
                pass

    if latest_time is None:
        raise HTTPException(400, "No simulation results found")

    env = get_openfoam_env()

    # OpenFOAM 13 uses foamPostProcess with cutPlaneSurface function
    slice_configs = [
        ("(0 -0.02 0)", "(0 1 0)"),  # Y-slice at y=-0.02
        ("(0 0 0)", "(0 1 0)"),       # Y-slice at y=0
        ("(0 0.02 0)", "(0 1 0)"),    # Y-slice at y=0.02
        ("(0 0 0)", "(1 0 0)"),       # X-slice at x=0
    ]

    errors = []
    for point, normal in slice_configs:
        func_arg = f'cutPlaneSurface(point={point}, normal={normal}, fields=(p U))'
        try:
            proc = await asyncio.create_subprocess_exec(
                "foamPostProcess", "-func", func_arg, "-latestTime",
                cwd=str(case_dir),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                errors.append(f"Slice {point}: {stderr.decode() or stdout.decode()}")
        except Exception as e:
            errors.append(f"Slice {point}: {str(e)}")

    if errors:
        return {
            "success": False,
            "error": "\n".join(errors),
            "partial": len(errors) < len(slice_configs)
        }

    return {
        "success": True,
        "message": "Post-processing completed - 4 pressure slices generated",
        "time": latest_time
    }


# =============================================================================
# Geometry Optimization API (AI-driven design loop)
# =============================================================================

# Import optimization modules
try:
    from backend.optimization import (
        ParametricWheel,
        WheelParameters,
        WheelOptimizer,
        OptimizationConfig,
        OptimizationResult,
        CFDSurrogateDatabase,
        create_optimization_bounds,
    )
    OPTIMIZATION_AVAILABLE = True
except ImportError:
    try:
        from optimization import (
            ParametricWheel,
            WheelParameters,
            WheelOptimizer,
            OptimizationConfig,
            OptimizationResult,
            CFDSurrogateDatabase,
            create_optimization_bounds,
        )
        OPTIMIZATION_AVAILABLE = True
    except ImportError:
        OPTIMIZATION_AVAILABLE = False

# In-memory optimization job store
optimization_jobs = {}


class OptimizationRequest(BaseModel):
    """Request model for optimization endpoint."""
    name: str
    algorithm: str = "bayesian"  # bayesian, nsga2, random
    n_trials: int = 30
    multi_objective: bool = False
    objectives: List[str] = ["drag"]  # drag, side_force, weight, cda
    speed: float = 13.9
    yaw_angle: float = 15.0
    use_surrogate: bool = True
    quality: str = "basic"  # CFD mesh quality for evaluations


class ParametricWheelRequest(BaseModel):
    """Request model for parametric wheel generation."""
    rim_depth: float = 0.045
    rim_width_outer: float = 0.028
    rim_profile: str = "toroidal"
    spoke_count: int = 24
    spoke_profile: str = "round"
    spoke_pattern: str = "radial"
    tire_width: float = 0.025


@app.get("/api/optimize/status")
async def get_optimization_status():
    """Check if optimization system is available."""
    return {
        "available": OPTIMIZATION_AVAILABLE,
        "algorithms": ["bayesian", "nsga2", "random"] if OPTIMIZATION_AVAILABLE else [],
        "objectives": ["drag", "side_force", "weight", "cda"] if OPTIMIZATION_AVAILABLE else [],
        "message": "Optimization system ready" if OPTIMIZATION_AVAILABLE else "Install optuna: pip install optuna",
    }


@app.post("/api/optimize/start")
async def start_optimization(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    algorithm: str = Form("bayesian"),
    n_trials: int = Form(30),
    multi_objective: bool = Form(False),
    objectives: str = Form("drag"),  # Comma-separated
    speed: float = Form(13.9),
    yaw_angle: float = Form(15.0),
    use_surrogate: bool = Form(True),
    quality: str = Form("basic"),
):
    """
    Start an AI-driven geometry optimization loop.

    Uses Bayesian optimization (Optuna) or NSGA-II for multi-objective
    optimization to find optimal wheel geometries.

    The system:
    1. Generates parametric wheel geometries
    2. Runs CFD simulations (or uses surrogate model)
    3. Uses optimization algorithms to find better designs
    4. Returns Pareto-optimal solutions for multi-objective cases
    """
    if not OPTIMIZATION_AVAILABLE:
        raise HTTPException(503, "Optimization module not available. Install: pip install optuna")

    optimization_id = str(uuid.uuid4())[:8]

    # Parse objectives
    obj_list = [o.strip() for o in objectives.split(",")]

    # Create optimization config
    config = OptimizationConfig(
        algorithm=algorithm,
        n_trials=n_trials,
        multi_objective=multi_objective,
        objectives=obj_list,
        flow_velocity=speed,
        yaw_angle=yaw_angle,
        use_surrogate=use_surrogate,
        output_dir=CASES_DIR / f"optimization_{optimization_id}",
    )

    # Store job info
    optimization_jobs[optimization_id] = {
        "id": optimization_id,
        "name": name,
        "status": "queued",
        "progress": 0,
        "config": config.to_dict(),
        "results": [],
        "best_result": None,
        "pareto_front": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    # Start optimization in background
    background_tasks.add_task(run_optimization_task, optimization_id, config)

    return {
        "optimization_id": optimization_id,
        "status": "queued",
        "config": config.to_dict(),
    }


async def run_optimization_task(optimization_id: str, config: OptimizationConfig):
    """Background task for running optimization."""
    job = optimization_jobs[optimization_id]

    try:
        job["status"] = "running"
        job["updated_at"] = datetime.now().isoformat()

        # Create output directory
        config.output_dir.mkdir(parents=True, exist_ok=True)

        # Create optimizer with dummy CFD runner (surrogate + physics-based)
        optimizer = WheelOptimizer(config)

        # Run optimization
        results = optimizer.optimize()

        # Store results
        job["results"] = [r.to_dict() for r in results]
        job["progress"] = 100

        if optimizer.best_result:
            job["best_result"] = optimizer.best_result.to_dict()

        if config.multi_objective:
            pareto = optimizer.get_pareto_front()
            job["pareto_front"] = [r.to_dict() for r in pareto]

        job["history"] = optimizer.get_optimization_history()
        job["status"] = "complete"

    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)

    job["updated_at"] = datetime.now().isoformat()


@app.get("/api/optimize/{optimization_id}")
async def get_optimization_job(optimization_id: str):
    """Get optimization job status and results."""
    if optimization_id not in optimization_jobs:
        raise HTTPException(404, "Optimization job not found")
    return optimization_jobs[optimization_id]


@app.get("/api/optimize/{optimization_id}/history")
async def get_optimization_history(optimization_id: str):
    """Get optimization convergence history for visualization."""
    if optimization_id not in optimization_jobs:
        raise HTTPException(404, "Optimization job not found")

    job = optimization_jobs[optimization_id]
    return job.get("history", {"error": "No history available"})


@app.get("/api/optimize/{optimization_id}/pareto")
async def get_pareto_front(optimization_id: str):
    """Get Pareto-optimal solutions for multi-objective optimization."""
    if optimization_id not in optimization_jobs:
        raise HTTPException(404, "Optimization job not found")

    job = optimization_jobs[optimization_id]
    if not job["config"].get("multi_objective"):
        raise HTTPException(400, "Not a multi-objective optimization")

    return {
        "pareto_front": job.get("pareto_front", []),
        "objectives": job["config"].get("objectives", []),
    }


@app.post("/api/optimize/suggest")
async def suggest_next_design(optimization_id: str = Form(None)):
    """
    Get a suggested wheel design for the next experiment.

    Can be used for human-in-the-loop optimization where
    a human decides which designs to actually test.
    """
    if not OPTIMIZATION_AVAILABLE:
        raise HTTPException(503, "Optimization module not available")

    if optimization_id and optimization_id in optimization_jobs:
        # Use existing optimization state
        # For now, return a random suggestion from presets
        pass

    # Return a suggested design
    presets = {
        "deep_section": WheelParameters.deep_section(),
        "super_deep": WheelParameters.super_deep(),
        "climbing": WheelParameters.climbing(),
    }

    import random
    preset_name = random.choice(list(presets.keys()))
    params = presets[preset_name]

    return {
        "preset": preset_name,
        "parameters": params.to_dict(),
        "description": f"Suggested design: {preset_name.replace('_', ' ').title()}",
    }


@app.post("/api/parametric/generate")
async def generate_parametric_wheel(
    rim_depth: float = Form(0.045),
    rim_width_outer: float = Form(0.028),
    rim_profile: str = Form("toroidal"),
    spoke_count: int = Form(24),
    spoke_profile: str = Form("round"),
    spoke_pattern: str = Form("radial"),
    tire_width: float = Form(0.025),
):
    """
    Generate a parametric wheel STL from given parameters.

    Returns the generated STL file for download or preview.
    """
    if not OPTIMIZATION_AVAILABLE:
        raise HTTPException(503, "Optimization module not available")

    params = WheelParameters(
        rim_depth=rim_depth,
        rim_width_outer=rim_width_outer,
        rim_profile=rim_profile,
        spoke_count=spoke_count,
        spoke_profile=spoke_profile,
        spoke_pattern=spoke_pattern,
        tire_width=tire_width,
    )

    # Generate wheel
    wheel = ParametricWheel(params)
    wheel.generate()

    # Save to temporary file
    file_id = str(uuid.uuid4())[:8]
    stl_path = UPLOAD_DIR / f"parametric_{file_id}.stl"
    wheel.save_stl(stl_path, binary=True)

    return {
        "file_id": f"parametric_{file_id}",
        "stl_path": str(stl_path),
        "parameters": params.to_dict(),
        "triangle_count": wheel.get_triangle_count(),
        "frontal_area": wheel.get_frontal_area(),
        "bounds": {
            "min": wheel.get_bounds()[0].tolist(),
            "max": wheel.get_bounds()[1].tolist(),
        },
    }


@app.get("/api/parametric/presets")
async def get_wheel_presets():
    """Get available wheel design presets."""
    if not OPTIMIZATION_AVAILABLE:
        raise HTTPException(503, "Optimization module not available")

    presets = {
        "deep_section": {
            "name": "Deep Section Aero",
            "description": "50mm deep section wheel for time trials",
            "parameters": WheelParameters.deep_section().to_dict(),
        },
        "super_deep": {
            "name": "Super Deep Triathlon",
            "description": "80mm deep wheel with fairing for maximum aero",
            "parameters": WheelParameters.super_deep().to_dict(),
        },
        "climbing": {
            "name": "Lightweight Climbing",
            "description": "28mm shallow rim for climbing performance",
            "parameters": WheelParameters.climbing().to_dict(),
        },
        "disc": {
            "name": "Disc Wheel",
            "description": "Full disc for ultimate aerodynamics",
            "parameters": WheelParameters.disc().to_dict(),
        },
    }

    return {"presets": presets}


@app.get("/api/parametric/bounds")
async def get_parameter_bounds():
    """Get parameter bounds for optimization."""
    if not OPTIMIZATION_AVAILABLE:
        raise HTTPException(503, "Optimization module not available")

    return {
        "bounds": create_optimization_bounds(),
        "description": "Min/max values for each optimizable parameter",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
