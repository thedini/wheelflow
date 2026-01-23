"""
Force Distribution Visualization
Extracts and processes force coefficient data from OpenFOAM postProcessing
"""

from pathlib import Path
from typing import Dict, List, Optional
import re


def extract_force_distribution(case_dir: Path) -> Dict:
    """
    Extract force coefficient history from forceCoeffs postProcessing data.

    Returns dict with:
    - time: list of time steps
    - Cd: drag coefficient history
    - Cl: lift coefficient history
    - Cm: moment coefficient history
    - converged: bool indicating if simulation converged
    - final_values: dict with final Cd, Cl, Cm
    """
    force_file = case_dir / "postProcessing" / "forceCoeffs" / "0" / "forceCoeffs.dat"

    result = {
        "time": [],
        "Cd": [],
        "Cl": [],
        "Cm": [],
        "Cl_front": [],
        "Cl_rear": [],
        "converged": False,
        "final_values": {}
    }

    if not force_file.exists():
        return result

    try:
        with open(force_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue

                parts = line.split()
                if len(parts) >= 6:
                    # Columns: Time, Cm, Cd, Cl, Cl(f), Cl(r)
                    result["time"].append(float(parts[0]))
                    result["Cm"].append(float(parts[1]))
                    result["Cd"].append(float(parts[2]))
                    result["Cl"].append(float(parts[3]))
                    result["Cl_front"].append(float(parts[4]))
                    result["Cl_rear"].append(float(parts[5]))

        if result["time"]:
            result["converged"] = True
            result["final_values"] = {
                "Cd": result["Cd"][-1],
                "Cl": result["Cl"][-1],
                "Cm": result["Cm"][-1],
                "time": result["time"][-1]
            }

            # Check convergence by looking at last 50 iterations
            if len(result["Cd"]) >= 50:
                recent_cd = result["Cd"][-50:]
                cd_variation = max(recent_cd) - min(recent_cd)
                result["converged"] = cd_variation < 0.01  # Less than 1% variation

    except Exception as e:
        result["error"] = str(e)

    return result


def extract_convergence_history(case_dir: Path) -> Dict:
    """
    Extract residual history from OpenFOAM log files.

    Returns dict with residual histories for p, U, k, omega
    """
    result = {
        "iterations": [],
        "p": [],
        "Ux": [],
        "Uy": [],
        "Uz": [],
        "k": [],
        "omega": []
    }

    # Try to find solver log
    log_files = list(case_dir.glob("log.*")) + list(case_dir.glob("*.log"))

    for log_file in log_files:
        try:
            with open(log_file, 'r') as f:
                content = f.read()

            # Parse residuals using regex
            # Pattern: "Solving for p, Initial residual = 0.123, Final residual = 0.001"
            p_pattern = r"Solving for p,.*?Initial residual = ([\d.e+-]+)"
            ux_pattern = r"Solving for Ux,.*?Initial residual = ([\d.e+-]+)"
            k_pattern = r"Solving for k,.*?Initial residual = ([\d.e+-]+)"
            omega_pattern = r"Solving for omega,.*?Initial residual = ([\d.e+-]+)"

            p_matches = re.findall(p_pattern, content)
            ux_matches = re.findall(ux_pattern, content)
            k_matches = re.findall(k_pattern, content)
            omega_matches = re.findall(omega_pattern, content)

            if p_matches:
                result["p"] = [float(x) for x in p_matches]
                result["iterations"] = list(range(1, len(p_matches) + 1))
            if ux_matches:
                result["Ux"] = [float(x) for x in ux_matches]
            if k_matches:
                result["k"] = [float(x) for x in k_matches]
            if omega_matches:
                result["omega"] = [float(x) for x in omega_matches]

            if result["iterations"]:
                break  # Found data, stop searching

        except Exception:
            continue

    return result


def calculate_forces(coefficients: Dict, config: Dict) -> Dict:
    """
    Calculate actual forces from coefficients.

    Args:
        coefficients: dict with Cd, Cl, Cm
        config: simulation config with speed, air properties, reference area

    Returns:
        dict with drag_N, lift_N, moment_Nm, CdA, dynamic_pressure
    """
    rho = config.get("air", {}).get("rho", 1.225)
    U = config.get("speed", 13.9)

    # Calculate reference area from wheel geometry if available
    # For now use a reasonable default based on wheel diameter
    wheel_radius = config.get("wheel_radius", 0.325)
    wheel_diameter = wheel_radius * 2

    # Frontal area approximation: width * height
    # For a wheel, approximate as ellipse: pi * r_width * r_height
    # Typical tire width ~28mm, wheel height = diameter
    tire_width = 0.028  # 28mm tire
    Aref = 0.5 * 3.14159 * (tire_width / 2) * wheel_radius  # Semi-ellipse area

    # Or use the AeroCloud reference area
    Aref = 0.0225  # m² - matches AeroCloud

    q = 0.5 * rho * U * U  # Dynamic pressure

    Cd = coefficients.get("Cd", 0)
    Cl = coefficients.get("Cl", 0)
    Cm = coefficients.get("Cm", 0)

    return {
        "drag_N": Cd * q * Aref,
        "lift_N": Cl * q * Aref,
        "moment_Nm": Cm * q * Aref * wheel_diameter,
        "CdA": Cd * Aref,
        "CdA_cm2": Cd * Aref * 10000,  # Convert to cm²
        "dynamic_pressure": q,
        "reference_area": Aref,
        "Cd": Cd,
        "Cl": Cl,
        "Cm": Cm
    }


def extract_yaw_series(case_dirs: List[Path], yaw_angles: List[float]) -> Dict:
    """
    Extract force data across multiple yaw angles for polar plots.

    Args:
        case_dirs: list of case directories for each yaw angle
        yaw_angles: corresponding yaw angles in degrees

    Returns:
        dict with yaw angles and corresponding Cd, Cl, Cs values
    """
    result = {
        "yaw_angles": yaw_angles,
        "Cd": [],
        "Cl": [],
        "Cs": [],  # Side force coefficient
        "drag_N": [],
        "side_N": []
    }

    for case_dir in case_dirs:
        force_data = extract_force_distribution(case_dir)
        if force_data.get("final_values"):
            result["Cd"].append(force_data["final_values"]["Cd"])
            result["Cl"].append(force_data["final_values"]["Cl"])
            # Side force would need separate extraction
            result["Cs"].append(0)  # Placeholder
        else:
            result["Cd"].append(None)
            result["Cl"].append(None)
            result["Cs"].append(None)

    return result
