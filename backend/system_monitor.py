"""
System Resource Monitoring for WheelFlow
Real-time CPU, GPU, RAM, and process monitoring
"""

import os
import subprocess
import psutil
from pathlib import Path
from typing import Dict, Optional
import re


def get_system_stats() -> Dict:
    """
    Get comprehensive system statistics.

    Returns dict with CPU, RAM, GPU, and process info.
    """
    stats = {
        "cpu": get_cpu_stats(),
        "memory": get_memory_stats(),
        "gpu": get_gpu_stats(),
        "openfoam": get_openfoam_processes(),
        "disk": get_disk_stats()
    }
    return stats


def get_cpu_stats() -> Dict:
    """Get CPU usage statistics."""
    try:
        # Overall CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Per-core usage
        per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)

        # CPU frequency
        freq = psutil.cpu_freq()

        # Load average (1, 5, 15 min)
        load = os.getloadavg()

        return {
            "percent": cpu_percent,
            "per_core": per_cpu,
            "cores": psutil.cpu_count(),
            "physical_cores": psutil.cpu_count(logical=False),
            "frequency_mhz": freq.current if freq else 0,
            "frequency_max_mhz": freq.max if freq else 0,
            "load_1min": load[0],
            "load_5min": load[1],
            "load_15min": load[2]
        }
    except Exception as e:
        return {"error": str(e), "percent": 0}


def get_memory_stats() -> Dict:
    """Get RAM and swap usage."""
    try:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return {
            "total_gb": mem.total / (1024**3),
            "used_gb": mem.used / (1024**3),
            "available_gb": mem.available / (1024**3),
            "percent": mem.percent,
            "cached_gb": getattr(mem, 'cached', 0) / (1024**3),
            "buffers_gb": getattr(mem, 'buffers', 0) / (1024**3),
            "swap_total_gb": swap.total / (1024**3),
            "swap_used_gb": swap.used / (1024**3),
            "swap_percent": swap.percent
        }
    except Exception as e:
        return {"error": str(e), "percent": 0}


def get_gpu_stats() -> Dict:
    """Get NVIDIA GPU statistics using nvidia-smi."""
    gpu_stats = {
        "available": False,
        "devices": []
    }

    try:
        # Query GPU info
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits"
            ],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            gpu_stats["available"] = True

            for line in result.stdout.strip().split('\n'):
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 8:
                    gpu_stats["devices"].append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "memory_total_mb": float(parts[2]),
                        "memory_used_mb": float(parts[3]),
                        "memory_free_mb": float(parts[4]),
                        "utilization_percent": float(parts[5]) if parts[5] != '[N/A]' else 0,
                        "temperature_c": float(parts[6]) if parts[6] != '[N/A]' else 0,
                        "power_w": float(parts[7]) if parts[7] != '[N/A]' else 0
                    })

    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
        gpu_stats["error"] = str(e)

    return gpu_stats


def get_openfoam_processes() -> Dict:
    """Get OpenFOAM-related process statistics."""
    of_stats = {
        "processes": [],
        "total_cpu": 0,
        "total_memory_mb": 0,
        "active_solver": None,
        "mpi_ranks": 0
    }

    # OpenFOAM process names to look for
    of_processes = [
        'blockMesh', 'snappyHexMesh', 'simpleFoam', 'pimpleFoam',
        'decomposePar', 'reconstructPar', 'checkMesh', 'surfaceFeatures',
        'potentialFoam', 'createPatch'
    ]

    try:
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'cmdline']):
            try:
                pinfo = proc.info
                name = pinfo['name']

                # Check if it's an OpenFOAM process
                is_of = any(of_name in name for of_name in of_processes)

                # Also check command line for mpirun with OpenFOAM
                cmdline = pinfo.get('cmdline', [])
                if cmdline and not is_of:
                    cmdline_str = ' '.join(cmdline)
                    is_of = any(of_name in cmdline_str for of_name in of_processes)
                    if 'mpirun' in name or 'mpiexec' in name:
                        is_of = True

                if is_of:
                    mem_mb = pinfo['memory_info'].rss / (1024**2) if pinfo['memory_info'] else 0
                    cpu = pinfo['cpu_percent'] or 0

                    proc_info = {
                        "pid": pinfo['pid'],
                        "name": name,
                        "cpu_percent": cpu,
                        "memory_mb": mem_mb
                    }
                    of_stats["processes"].append(proc_info)
                    of_stats["total_cpu"] += cpu
                    of_stats["total_memory_mb"] += mem_mb

                    # Identify active solver
                    for solver in ['simpleFoam', 'pimpleFoam', 'snappyHexMesh', 'blockMesh']:
                        if solver in name or (cmdline and solver in ' '.join(cmdline)):
                            of_stats["active_solver"] = solver
                            break

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Count MPI ranks
        of_stats["mpi_ranks"] = len([p for p in of_stats["processes"]
                                     if 'Foam' in p['name'] or 'Mesh' in p['name']])

    except Exception as e:
        of_stats["error"] = str(e)

    return of_stats


def get_disk_stats(path: str = None) -> Dict:
    """Get disk usage statistics."""
    if path is None:
        path = str(Path.home())

    try:
        usage = psutil.disk_usage(path)

        # Get I/O stats
        io = psutil.disk_io_counters()

        return {
            "total_gb": usage.total / (1024**3),
            "used_gb": usage.used / (1024**3),
            "free_gb": usage.free / (1024**3),
            "percent": usage.percent,
            "read_mb": io.read_bytes / (1024**2) if io else 0,
            "write_mb": io.write_bytes / (1024**2) if io else 0
        }
    except Exception as e:
        return {"error": str(e), "percent": 0}


def get_openfoam_progress(case_dir: Path) -> Dict:
    """
    Parse OpenFOAM log to get solver progress.

    Returns iteration count, residuals, and time info.
    """
    progress = {
        "iteration": 0,
        "time": 0.0,
        "residuals": {
            "p": None,
            "Ux": None,
            "Uy": None,
            "k": None,
            "omega": None
        },
        "continuity_error": None,
        "execution_time": 0.0,
        "clock_time": 0.0
    }

    # Find log file
    log_patterns = ['log.simpleFoam', 'log.pimpleFoam', 'log.snappyHexMesh', 'log.blockMesh']

    for pattern in log_patterns:
        log_file = case_dir / pattern
        if log_file.exists():
            try:
                # Read last portion of log (last 100KB)
                with open(log_file, 'rb') as f:
                    f.seek(0, 2)  # End of file
                    size = f.tell()
                    f.seek(max(0, size - 102400))  # Last 100KB
                    content = f.read().decode('utf-8', errors='ignore')

                # Parse iteration/time
                time_matches = re.findall(r'Time = (\d+\.?\d*)', content)
                if time_matches:
                    progress["time"] = float(time_matches[-1])
                    progress["iteration"] = int(float(time_matches[-1]))

                # Parse residuals
                for field in ['p', 'Ux', 'Uy', 'Uz', 'k', 'omega']:
                    pattern = rf'Solving for {field},.*?Initial residual = ([\d.e+-]+)'
                    matches = re.findall(pattern, content)
                    if matches:
                        progress["residuals"][field] = float(matches[-1])

                # Parse continuity error
                cont_matches = re.findall(r'continuity errors : sum local = ([\d.e+-]+)', content)
                if cont_matches:
                    progress["continuity_error"] = float(cont_matches[-1])

                # Parse execution time
                exec_matches = re.findall(r'ExecutionTime = ([\d.]+) s', content)
                if exec_matches:
                    progress["execution_time"] = float(exec_matches[-1])

                clock_matches = re.findall(r'ClockTime = ([\d.]+) s', content)
                if clock_matches:
                    progress["clock_time"] = float(clock_matches[-1])

                break

            except Exception as e:
                progress["error"] = str(e)

    return progress


def format_bytes(bytes_val: float) -> str:
    """Format bytes into human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(bytes_val) < 1024.0:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} PB"
