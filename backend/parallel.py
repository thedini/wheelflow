"""
Parallel Processing Support for WheelFlow
Handles MPI-based parallel execution and GPU acceleration planning
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, List
import multiprocessing


def get_system_info() -> Dict:
    """
    Get system information for parallel processing.
    """
    info = {
        "cpu_count": multiprocessing.cpu_count(),
        "mpi_available": shutil.which("mpirun") is not None,
        "decompose_available": False,
        "gpu_available": False,
        "gpu_info": None
    }

    # Check for OpenFOAM decomposePar
    openfoam_bin = Path("/opt/openfoam13/platforms/linux64GccDPInt32Opt/bin")
    if (openfoam_bin / "decomposePar").exists():
        info["decompose_available"] = True

    # Check for GPU (NVIDIA)
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            info["gpu_available"] = True
            info["gpu_info"] = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return info


def generate_decompose_dict(case_dir: Path, num_procs: int, method: str = "scotch") -> str:
    """
    Generate decomposeParDict for parallel decomposition.

    Args:
        case_dir: OpenFOAM case directory
        num_procs: Number of processors
        method: Decomposition method (scotch, hierarchical, simple)

    Returns:
        Path to generated decomposeParDict
    """
    decompose_dict = f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      decomposeParDict;
}}

numberOfSubdomains {num_procs};

method          {method};

simpleCoeffs
{{
    n               ({_factorize(num_procs)});
    delta           0.001;
}}

hierarchicalCoeffs
{{
    n               ({_factorize(num_procs)});
    delta           0.001;
    order           xyz;
}}

scotchCoeffs
{{
    // No additional parameters needed
}}

distributed     no;

roots           ();
"""

    dict_path = case_dir / "system" / "decomposeParDict"
    dict_path.write_text(decompose_dict)
    return str(dict_path)


def _factorize(n: int) -> str:
    """
    Factorize number into 3 factors for domain decomposition.
    Tries to make factors as equal as possible.
    """
    factors = []

    # Find factors
    for i in [2, 3, 5, 7]:
        while n % i == 0:
            factors.append(i)
            n //= i
    if n > 1:
        factors.append(n)

    # Distribute into 3 groups
    result = [1, 1, 1]
    for f in sorted(factors, reverse=True):
        # Add to smallest
        min_idx = result.index(min(result))
        result[min_idx] *= f

    return f"{result[0]} {result[1]} {result[2]}"


async def run_parallel_command(
    case_dir: Path,
    command: str,
    args: List[str] = None,
    num_procs: int = None,
    openfoam_dir: Path = None
) -> Dict:
    """
    Run OpenFOAM command in parallel using MPI.

    Args:
        case_dir: OpenFOAM case directory
        command: OpenFOAM command (e.g., "snappyHexMesh", "simpleFoam")
        args: Additional command arguments
        num_procs: Number of processors (default: auto-detect)
        openfoam_dir: OpenFOAM installation directory

    Returns:
        Dict with stdout, stderr, return_code
    """
    import asyncio

    if args is None:
        args = []

    if openfoam_dir is None:
        openfoam_dir = Path("/opt/openfoam13")

    if num_procs is None:
        num_procs = max(1, multiprocessing.cpu_count() - 1)  # Leave 1 core free

    # Check if MPI is available
    if not shutil.which("mpirun"):
        raise RuntimeError("MPI not available. Install OpenMPI: apt-get install openmpi-bin")

    # Generate decomposeParDict if not exists
    decompose_dict = case_dir / "system" / "decomposeParDict"
    if not decompose_dict.exists():
        generate_decompose_dict(case_dir, num_procs)

    # Setup environment
    env = os.environ.copy()
    openfoam_bin = openfoam_dir / "platforms/linux64GccDPInt32Opt/bin"
    openfoam_lib = openfoam_dir / "platforms/linux64GccDPInt32Opt/lib"

    env["PATH"] = f"{openfoam_bin}:{env.get('PATH', '')}"
    env["LD_LIBRARY_PATH"] = f"{openfoam_lib}:{openfoam_lib}/dummy:{env.get('LD_LIBRARY_PATH', '')}"
    env["WM_PROJECT_DIR"] = str(openfoam_dir)
    env["FOAM_LIBBIN"] = str(openfoam_lib)

    result = {
        "command": command,
        "num_procs": num_procs,
        "parallel": True,
        "stdout": "",
        "stderr": "",
        "return_code": 0
    }

    try:
        # Step 1: Decompose the domain
        if command not in ["blockMesh", "decomposePar", "reconstructPar"]:
            decompose_proc = await asyncio.create_subprocess_exec(
                "decomposePar",
                cwd=case_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await decompose_proc.communicate()
            if decompose_proc.returncode != 0:
                result["stderr"] = f"decomposePar failed: {stderr.decode()}"
                result["return_code"] = decompose_proc.returncode
                return result

        # Step 2: Run parallel command
        cmd = ["mpirun", "-np", str(num_procs), command, "-parallel"] + args

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=case_dir,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()
        result["stdout"] = stdout.decode(errors='replace')
        result["stderr"] = stderr.decode(errors='replace')
        result["return_code"] = process.returncode

        # Step 3: Reconstruct the mesh/fields
        if process.returncode == 0 and command not in ["blockMesh", "decomposePar"]:
            if command == "snappyHexMesh":
                reconstruct_cmd = ["reconstructParMesh", "-constant"]
            else:
                reconstruct_cmd = ["reconstructPar"]

            reconstruct_proc = await asyncio.create_subprocess_exec(
                *reconstruct_cmd,
                cwd=case_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await reconstruct_proc.communicate()

    except Exception as e:
        result["stderr"] = str(e)
        result["return_code"] = 1

    return result


# =============================================================================
# GPU Acceleration Planning
# =============================================================================

GPU_ACCELERATION_PLAN = """
# GPU Acceleration for OpenFOAM

## Current Status
OpenFOAM does not natively support GPU acceleration. However, there are several
approaches to leverage GPU computing:

## Option 1: AmgX (NVIDIA)
- **What:** GPU-accelerated algebraic multigrid solver
- **Best for:** Pressure equation (GAMG replacement)
- **Speedup:** 2-5x for pressure solve
- **Requirements:**
  - NVIDIA GPU with CUDA
  - AmgX library compiled with OpenFOAM
  - Modified fvSolution to use AmgX solver

## Option 2: PETSc with CUDA
- **What:** Portable, Extensible Toolkit for Scientific Computation
- **Best for:** All linear solvers
- **Speedup:** 2-4x overall
- **Requirements:**
  - PETSc compiled with CUDA support
  - petsc4Foam plugin for OpenFOAM

## Option 3: OpenFOAM-GPU (RapidCFD)
- **What:** Fork of OpenFOAM with native CUDA support
- **Best for:** Full solver acceleration
- **Speedup:** 5-10x for supported solvers
- **Limitations:**
  - Not all solvers supported
  - May lag behind official OpenFOAM releases

## Option 4: NVIDIA Modulus (AI-based)
- **What:** Physics-informed neural networks
- **Best for:** Steady-state CFD, design optimization
- **Speedup:** 1000x+ for trained models
- **Limitations:**
  - Requires training data
  - Not suitable for all cases

## Recommended Implementation Path

### Phase 1: CPU Parallelization (Now)
- Use MPI with decomposePar
- Target: 4-8x speedup on 8-core system

### Phase 2: AmgX for Pressure (If NVIDIA GPU available)
- Install AmgX library
- Modify fvSolution to use AmgXGAMGSolver
- Target: Additional 2-3x speedup on pressure solve

### Phase 3: Evaluate Full GPU (Future)
- Test RapidCFD for specific wheel simulation
- Consider Modulus for design optimization

## fvSolution with AmgX (Example)

```cpp
solvers
{
    p
    {
        solver          AmgXGAMGSolver;
        AmgXConfig      "amgx_config.json";
        tolerance       1e-06;
        relTol          0.01;
    }

    pFinal
    {
        $p;
        relTol          0;
    }
}
```

## amgx_config.json (Example)

```json
{
    "config_version": 2,
    "solver": {
        "solver": "AMG",
        "presweeps": 2,
        "postsweeps": 2,
        "max_levels": 20,
        "cycle": "V",
        "coarsest_sweeps": 4,
        "coarse_solver": "DENSE_LU_SOLVER"
    }
}
```
"""


def get_gpu_acceleration_plan() -> str:
    """Return the GPU acceleration planning document."""
    return GPU_ACCELERATION_PLAN


def check_gpu_readiness() -> Dict:
    """
    Check if system is ready for GPU acceleration.
    """
    status = {
        "nvidia_driver": False,
        "cuda_toolkit": False,
        "amgx_available": False,
        "amgx_solver_compiled": False,
        "petsc_cuda": False,
        "recommendations": []
    }

    # Check NVIDIA driver
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
        status["nvidia_driver"] = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        status["recommendations"].append("Install NVIDIA driver: apt-get install nvidia-driver-535")

    # Check CUDA toolkit
    cuda_paths = ["/usr/local/cuda", "/usr/local/cuda-12", "/usr/local/cuda-12.9", "/usr/local/cuda-11"]
    for cuda_path in cuda_paths:
        if Path(cuda_path).exists():
            status["cuda_toolkit"] = True
            break
    if not status["cuda_toolkit"]:
        status["recommendations"].append("Install CUDA Toolkit: apt-get install nvidia-cuda-toolkit")

    # Check AmgX library (usually in /usr/local/amgx or custom path)
    amgx_paths = ["/usr/local/amgx", "/opt/amgx", str(Path.home() / "amgx"), str(Path.home() / "local/amgx")]
    for amgx_path in amgx_paths:
        if Path(amgx_path).exists():
            status["amgx_available"] = True
            break
    if not status["amgx_available"]:
        status["recommendations"].append("Install AmgX from: https://github.com/NVIDIA/AMGX")

    # Check for compiled amgxSolvers library
    amgx_solver_lib = Path.home() / "OpenFOAM/constantine-13/platforms/linux64GccDPInt32Opt/lib/libamgxSolvers.so"
    status["amgx_solver_compiled"] = amgx_solver_lib.exists()
    if not status["amgx_solver_compiled"] and status["amgx_available"]:
        status["recommendations"].append("Compile amgxSolvers for OpenFOAM")

    # Summary
    if status["nvidia_driver"] and status["cuda_toolkit"]:
        if status["amgx_solver_compiled"]:
            status["summary"] = "GPU acceleration ready with AmgX solver"
        elif status["amgx_available"]:
            status["summary"] = "AmgX available, compile amgxSolvers for OpenFOAM"
        else:
            status["summary"] = "GPU available, install AmgX for solver acceleration"
    elif status["nvidia_driver"]:
        status["summary"] = "NVIDIA GPU detected, install CUDA toolkit"
    else:
        status["summary"] = "No NVIDIA GPU detected, using CPU only"

    return status
