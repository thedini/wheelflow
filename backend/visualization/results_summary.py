"""
Results Summary Generation
Compiles all simulation results into a structured summary
"""

from pathlib import Path
from typing import Dict, Optional
from .force_distribution import extract_force_distribution, calculate_forces, extract_convergence_history


def generate_results_summary(case_dir: Path, config: Dict) -> Dict:
    """
    Generate comprehensive results summary for a simulation.

    Args:
        case_dir: Path to OpenFOAM case directory
        config: Simulation configuration dict

    Returns:
        Complete results summary dict
    """
    summary = {
        "case_id": case_dir.name,
        "config": {
            "name": config.get("name", "Unknown"),
            "speed": config.get("speed", 13.9),
            "speed_kmh": config.get("speed", 13.9) * 3.6,
            "yaw_angles": config.get("yaw_angles", [0.0]),
            "wheel_radius": config.get("wheel_radius", 0.325),
            "wheel_diameter": config.get("wheel_radius", 0.325) * 2,
            "quality": config.get("quality", "standard"),
            "reynolds": config.get("reynolds", 0),
        },
        "mesh": get_mesh_info(case_dir),
        "convergence": {},
        "coefficients": {},
        "forces": {},
        "comparison": {},
        "visualizations": {
            "available": [],
            "paths": {}
        }
    }

    # Extract force coefficients
    force_data = extract_force_distribution(case_dir)
    if force_data.get("final_values"):
        summary["coefficients"] = force_data["final_values"]
        summary["convergence"]["converged"] = force_data["converged"]
        summary["convergence"]["iterations"] = int(force_data["final_values"].get("time", 0))

        # Calculate actual forces
        forces = calculate_forces(force_data["final_values"], config)
        summary["forces"] = forces

    # Extract convergence history
    conv_history = extract_convergence_history(case_dir)
    if conv_history.get("iterations"):
        summary["convergence"]["history"] = {
            "iterations": conv_history["iterations"],
            "residuals": {
                "p": conv_history.get("p", []),
                "Ux": conv_history.get("Ux", []),
                "k": conv_history.get("k", []),
                "omega": conv_history.get("omega", [])
            }
        }

    # Compare with AeroCloud reference
    summary["comparison"] = compare_with_reference(summary["forces"], config)

    # Check available visualizations
    viz_dir = case_dir / "visualizations"
    if viz_dir.exists():
        if (viz_dir / "hero.png").exists():
            summary["visualizations"]["available"].append("hero_image")
            summary["visualizations"]["paths"]["hero_image"] = "hero.png"
        if (viz_dir / "pressure_surface.ply").exists():
            summary["visualizations"]["available"].append("pressure_3d")
            summary["visualizations"]["paths"]["pressure_3d"] = "pressure_surface.ply"
        if (viz_dir / "slices").exists():
            summary["visualizations"]["available"].append("pressure_slices")
            summary["visualizations"]["paths"]["pressure_slices"] = "slices/"

    return summary


def get_mesh_info(case_dir: Path) -> Dict:
    """
    Extract mesh information from checkMesh output or polyMesh files.
    """
    mesh_info = {
        "cells": 0,
        "faces": 0,
        "points": 0,
        "quality": {}
    }

    # Try to read from polyMesh
    poly_mesh = case_dir / "constant" / "polyMesh"
    if poly_mesh.exists():
        # Count cells from owner file
        owner_file = poly_mesh / "owner"
        if owner_file.exists():
            try:
                with open(owner_file, 'r') as f:
                    content = f.read()
                    # Find the number in parentheses after FoamFile block
                    import re
                    match = re.search(r'\n(\d+)\n\(', content)
                    if match:
                        mesh_info["faces"] = int(match.group(1))
            except Exception:
                pass

        # Count points
        points_file = poly_mesh / "points"
        if points_file.exists():
            try:
                with open(points_file, 'r') as f:
                    content = f.read()
                    import re
                    match = re.search(r'\n(\d+)\n\(', content)
                    if match:
                        mesh_info["points"] = int(match.group(1))
            except Exception:
                pass

        # Estimate cells from faces (rough approximation)
        # For hex mesh: cells ≈ faces / 6
        if mesh_info["faces"] > 0:
            mesh_info["cells"] = mesh_info["faces"] // 6

    return mesh_info


def compare_with_reference(forces: Dict, config: Dict) -> Dict:
    """
    Compare results with AeroCloud reference values.

    AeroCloud TTTR28_22_TSV3 at 15° yaw:
    - Fd = 1.31 N
    - Cd = 0.490
    - CdA = 0.011 m²
    """
    reference = {
        "source": "AeroCloud TTTR28_22_TSV3",
        "yaw_angle": 15.0,
        "drag_N": 1.31,
        "Cd": 0.490,
        "CdA": 0.011,
        "side_N": 14.10,
        "Cs": 5.253,
        "yaw_moment_Nm": 4.34
    }

    current_yaw = config.get("yaw_angles", [0.0])[0]
    comparison = {
        "reference": reference,
        "current_yaw": current_yaw,
        "yaw_match": abs(current_yaw - reference["yaw_angle"]) < 1.0,
        "differences": {}
    }

    if forces:
        if forces.get("drag_N"):
            diff = (forces["drag_N"] - reference["drag_N"]) / reference["drag_N"] * 100
            comparison["differences"]["drag_N"] = {
                "value": forces["drag_N"],
                "reference": reference["drag_N"],
                "percent_diff": round(diff, 1)
            }

        if forces.get("CdA"):
            diff = (forces["CdA"] - reference["CdA"]) / reference["CdA"] * 100
            comparison["differences"]["CdA"] = {
                "value": forces["CdA"],
                "reference": reference["CdA"],
                "percent_diff": round(diff, 1)
            }

        if forces.get("Cd"):
            diff = (forces["Cd"] - reference["Cd"]) / reference["Cd"] * 100
            comparison["differences"]["Cd"] = {
                "value": forces["Cd"],
                "reference": reference["Cd"],
                "percent_diff": round(diff, 1)
            }

    # Add note about yaw angle difference
    if not comparison["yaw_match"]:
        comparison["note"] = f"Results at {current_yaw}° yaw, reference at {reference['yaw_angle']}° yaw. Direct comparison not valid."

    return comparison


def format_results_text(summary: Dict) -> str:
    """
    Format results summary as human-readable text.
    """
    lines = []
    lines.append("=" * 60)
    lines.append(f"WheelFlow CFD Results - {summary['config']['name']}")
    lines.append("=" * 60)

    lines.append(f"\nSimulation Settings:")
    lines.append(f"  Speed: {summary['config']['speed']:.1f} m/s ({summary['config']['speed_kmh']:.1f} km/h)")
    lines.append(f"  Yaw Angle: {summary['config']['yaw_angles'][0]}°")
    lines.append(f"  Wheel Diameter: {summary['config']['wheel_diameter']*1000:.1f} mm")
    lines.append(f"  Mesh Quality: {summary['config']['quality']}")
    lines.append(f"  Reynolds Number: {summary['config']['reynolds']:,.0f}")

    if summary.get("mesh", {}).get("cells"):
        lines.append(f"\nMesh Statistics:")
        lines.append(f"  Cells: {summary['mesh']['cells']:,}")

    if summary.get("convergence", {}).get("converged") is not None:
        lines.append(f"\nConvergence:")
        lines.append(f"  Status: {'Converged' if summary['convergence']['converged'] else 'Not converged'}")
        lines.append(f"  Iterations: {summary['convergence'].get('iterations', 'N/A')}")

    if summary.get("forces"):
        f = summary["forces"]
        lines.append(f"\nResults:")
        lines.append(f"  Drag Coefficient (Cd): {f.get('Cd', 0):.4f}")
        lines.append(f"  Lift Coefficient (Cl): {f.get('Cl', 0):.4f}")
        lines.append(f"  Drag Force: {f.get('drag_N', 0):.3f} N")
        lines.append(f"  Lift Force: {f.get('lift_N', 0):.3f} N")
        lines.append(f"  CdA: {f.get('CdA_cm2', 0):.1f} cm² ({f.get('CdA', 0):.6f} m²)")
        lines.append(f"  Reference Area: {f.get('reference_area', 0)*10000:.1f} cm²")

    if summary.get("comparison", {}).get("differences"):
        lines.append(f"\nComparison with AeroCloud:")
        comp = summary["comparison"]
        if comp.get("note"):
            lines.append(f"  Note: {comp['note']}")
        for key, diff in comp["differences"].items():
            lines.append(f"  {key}: {diff['value']:.4f} vs {diff['reference']:.4f} ({diff['percent_diff']:+.1f}%)")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)
