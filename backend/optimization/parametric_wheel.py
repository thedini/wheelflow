"""
Parametric Wheel Geometry Generator

Generates bicycle wheel STL geometry from parametric specifications.
Supports various rim profiles, spoke configurations, and tire shapes
for aerodynamic optimization studies.
"""

import math
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
import struct


@dataclass
class WheelParameters:
    """
    Complete parameterization of a bicycle wheel for CFD analysis.

    All dimensions in meters unless otherwise specified.
    Default values represent a typical 700c road wheel.
    """
    # Overall dimensions
    outer_diameter: float = 0.700  # 700c = 622mm bead + tire
    hub_diameter: float = 0.050   # Hub shell diameter
    hub_width: float = 0.040     # Hub shell width (flange to flange)

    # Rim parameters
    rim_depth: float = 0.045     # Rim depth (aero section)
    rim_width_outer: float = 0.028  # External width at widest point
    rim_width_inner: float = 0.019  # Internal width (tire bead seat)
    rim_profile: str = "toroidal"  # toroidal, v_shape, box, aero

    # Tire parameters
    tire_width: float = 0.025    # Tire section width
    tire_height: float = 0.025   # Tire section height
    tire_profile: str = "round"  # round, semi_slick, tubular

    # Spoke parameters
    spoke_count: int = 24        # Number of spokes
    spoke_diameter: float = 0.002  # Spoke thickness
    spoke_pattern: str = "radial"  # radial, 2cross, 3cross, paired
    spoke_profile: str = "round"   # round, bladed, aero
    spoke_blade_width: float = 0.004  # Width for bladed spokes

    # Advanced rim features
    rim_sidewall_curve: float = 0.5  # 0=straight, 1=full curve
    rim_trailing_edge: float = 0.003  # Trailing edge radius
    rim_fairing: bool = False    # Add fairing between spokes

    # Mesh resolution hints
    circumferential_segments: int = 120  # Around the wheel
    radial_segments: int = 20    # Across rim profile
    spoke_segments: int = 12     # Around spoke circumference

    def to_dict(self) -> Dict[str, Any]:
        """Convert parameters to dictionary for serialization."""
        return {
            'outer_diameter': self.outer_diameter,
            'hub_diameter': self.hub_diameter,
            'hub_width': self.hub_width,
            'rim_depth': self.rim_depth,
            'rim_width_outer': self.rim_width_outer,
            'rim_width_inner': self.rim_width_inner,
            'rim_profile': self.rim_profile,
            'tire_width': self.tire_width,
            'tire_height': self.tire_height,
            'tire_profile': self.tire_profile,
            'spoke_count': self.spoke_count,
            'spoke_diameter': self.spoke_diameter,
            'spoke_pattern': self.spoke_pattern,
            'spoke_profile': self.spoke_profile,
            'spoke_blade_width': self.spoke_blade_width,
            'rim_sidewall_curve': self.rim_sidewall_curve,
            'rim_trailing_edge': self.rim_trailing_edge,
            'rim_fairing': self.rim_fairing,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'WheelParameters':
        """Create parameters from dictionary."""
        return cls(**{k: v for k, v in d.items() if hasattr(cls, k)})

    @classmethod
    def deep_section(cls) -> 'WheelParameters':
        """Preset: Deep section aero wheel (50mm)."""
        return cls(
            rim_depth=0.050,
            rim_width_outer=0.027,
            rim_profile="toroidal",
            spoke_count=20,
            spoke_profile="bladed",
        )

    @classmethod
    def super_deep(cls) -> 'WheelParameters':
        """Preset: Super deep triathlon wheel (80mm)."""
        return cls(
            rim_depth=0.080,
            rim_width_outer=0.025,
            rim_profile="aero",
            spoke_count=18,
            spoke_profile="bladed",
            rim_fairing=True,
        )

    @classmethod
    def disc(cls) -> 'WheelParameters':
        """Preset: Disc wheel (full fairing)."""
        return cls(
            rim_depth=0.030,
            rim_width_outer=0.023,
            rim_profile="box",
            spoke_count=0,  # No visible spokes
            rim_fairing=True,  # Full disc
        )

    @classmethod
    def climbing(cls) -> 'WheelParameters':
        """Preset: Low profile climbing wheel (28mm)."""
        return cls(
            rim_depth=0.028,
            rim_width_outer=0.027,
            rim_profile="box",
            spoke_count=24,
            spoke_profile="round",
        )


class ParametricWheel:
    """
    Generates STL mesh for a parametric bicycle wheel.

    Coordinate system:
    - X: Axle direction (wheel thickness)
    - Y: Forward direction (rolling direction)
    - Z: Vertical (up)
    - Wheel center at origin
    - Ground contact at Z = -outer_radius
    """

    def __init__(self, params: WheelParameters):
        self.params = params
        self.triangles: List[Tuple[np.ndarray, np.ndarray, np.ndarray]] = []

    def generate(self) -> 'ParametricWheel':
        """Generate complete wheel geometry."""
        self.triangles = []

        # Generate components
        self._generate_rim()
        self._generate_tire()
        if self.params.spoke_count > 0:
            self._generate_spokes()
        self._generate_hub()

        if self.params.rim_fairing and self.params.spoke_count > 0:
            self._generate_spoke_fairing()
        elif self.params.rim_fairing and self.params.spoke_count == 0:
            self._generate_disc()

        return self

    def _generate_rim(self):
        """Generate rim geometry based on profile type."""
        p = self.params
        outer_r = p.outer_diameter / 2 - p.tire_height
        inner_r = outer_r - p.rim_depth

        n_circ = p.circumferential_segments
        n_rad = p.radial_segments

        # Generate rim profile points (in local 2D)
        profile = self._get_rim_profile(p.rim_profile)

        # Revolve profile around wheel axis
        for i in range(n_circ):
            theta1 = 2 * math.pi * i / n_circ
            theta2 = 2 * math.pi * (i + 1) / n_circ

            for j in range(len(profile) - 1):
                # Get profile points
                r1, x1 = profile[j]
                r2, x2 = profile[j + 1]

                # Scale radii from rim inner to outer
                actual_r1 = inner_r + r1 * p.rim_depth
                actual_r2 = inner_r + r2 * p.rim_depth

                # Scale x positions by rim width
                actual_x1 = x1 * p.rim_width_outer / 2
                actual_x2 = x2 * p.rim_width_outer / 2

                # Create quad vertices
                p1 = self._cylindrical_to_cartesian(actual_r1, theta1, actual_x1)
                p2 = self._cylindrical_to_cartesian(actual_r2, theta1, actual_x2)
                p3 = self._cylindrical_to_cartesian(actual_r2, theta2, actual_x2)
                p4 = self._cylindrical_to_cartesian(actual_r1, theta2, actual_x1)

                # Add two triangles for quad
                self.triangles.append((p1, p2, p3))
                self.triangles.append((p1, p3, p4))

    def _get_rim_profile(self, profile_type: str) -> List[Tuple[float, float]]:
        """
        Get rim cross-section profile as (radius_fraction, x_fraction) pairs.
        Radius: 0 = inner edge, 1 = outer edge
        X: -1 = left side, +1 = right side
        """
        n = self.params.radial_segments
        curve = self.params.rim_sidewall_curve

        if profile_type == "toroidal":
            # Smooth toroidal section (like Zipp/Enve)
            profile = []
            for i in range(n + 1):
                t = i / n  # 0 to 1 around profile
                if t < 0.3:
                    # Inner edge (flat bottom)
                    r = t / 0.3 * 0.1
                    x = -1 + t / 0.3 * 0.3
                elif t < 0.5:
                    # Left bulge
                    local_t = (t - 0.3) / 0.2
                    r = 0.1 + local_t * 0.9
                    x = -0.7 + curve * 0.3 * math.sin(local_t * math.pi)
                elif t < 0.7:
                    # Right bulge
                    local_t = (t - 0.5) / 0.2
                    r = 1.0 - local_t * 0.9
                    x = 0.7 - curve * 0.3 * math.sin(local_t * math.pi)
                else:
                    # Outer edge back to inner
                    local_t = (t - 0.7) / 0.3
                    r = 0.1 * (1 - local_t)
                    x = 0.7 + local_t * 0.3
                profile.append((r, x))
            return profile

        elif profile_type == "v_shape":
            # V-shaped profile (classic aero)
            return [
                (0.0, -0.5), (0.3, -0.8), (0.5, -1.0),
                (0.7, -0.8), (1.0, 0.0),
                (0.7, 0.8), (0.5, 1.0), (0.3, 0.8), (0.0, 0.5)
            ]

        elif profile_type == "box":
            # Box section (classic rim)
            return [
                (0.0, -0.8), (0.0, -1.0), (1.0, -1.0), (1.0, 1.0),
                (0.0, 1.0), (0.0, 0.8)
            ]

        elif profile_type == "aero":
            # Deep aero profile with sharp trailing edge
            profile = []
            for i in range(n + 1):
                t = i / n
                if t < 0.5:
                    # Front half (round leading edge)
                    angle = t * math.pi
                    r = 0.5 * (1 - math.cos(angle))
                    x = -math.sin(angle)
                else:
                    # Back half (tapered to trailing edge)
                    local_t = (t - 0.5) / 0.5
                    r = 1.0 - local_t
                    x = (1 - local_t) * (1 - local_t) - 1  # Curved taper
                profile.append((r, x))
            return profile

        else:
            # Default: simple rounded profile
            profile = []
            for i in range(n + 1):
                theta = math.pi * i / n
                r = 0.5 * (1 - math.cos(theta))
                x = -math.cos(theta)
                profile.append((r, x))
            return profile

    def _generate_tire(self):
        """Generate tire geometry."""
        p = self.params
        rim_outer_r = p.outer_diameter / 2 - p.tire_height
        tire_center_r = rim_outer_r + p.tire_height / 2

        n_circ = p.circumferential_segments
        n_section = p.radial_segments

        # Tire cross-section
        for i in range(n_circ):
            theta1 = 2 * math.pi * i / n_circ
            theta2 = 2 * math.pi * (i + 1) / n_circ

            for j in range(n_section):
                # Angle around tire cross-section
                phi1 = 2 * math.pi * j / n_section
                phi2 = 2 * math.pi * (j + 1) / n_section

                # Tire cross-section shape
                if p.tire_profile == "round":
                    # Circular cross-section
                    r1 = tire_center_r + (p.tire_height / 2) * math.cos(phi1)
                    r2 = tire_center_r + (p.tire_height / 2) * math.cos(phi2)
                    x1 = (p.tire_width / 2) * math.sin(phi1)
                    x2 = (p.tire_width / 2) * math.sin(phi2)
                else:
                    # Default to round
                    r1 = tire_center_r + (p.tire_height / 2) * math.cos(phi1)
                    r2 = tire_center_r + (p.tire_height / 2) * math.cos(phi2)
                    x1 = (p.tire_width / 2) * math.sin(phi1)
                    x2 = (p.tire_width / 2) * math.sin(phi2)

                # Create quad vertices
                p1 = self._cylindrical_to_cartesian(r1, theta1, x1)
                p2 = self._cylindrical_to_cartesian(r2, theta1, x2)
                p3 = self._cylindrical_to_cartesian(r2, theta2, x2)
                p4 = self._cylindrical_to_cartesian(r1, theta2, x1)

                self.triangles.append((p1, p2, p3))
                self.triangles.append((p1, p3, p4))

    def _generate_spokes(self):
        """Generate spoke geometry based on pattern."""
        p = self.params
        hub_r = p.hub_diameter / 2
        rim_inner_r = p.outer_diameter / 2 - p.tire_height - p.rim_depth

        # Spoke endpoints on hub flanges
        hub_x_left = -p.hub_width / 2
        hub_x_right = p.hub_width / 2

        for i in range(p.spoke_count):
            # Base angle for this spoke
            base_theta = 2 * math.pi * i / p.spoke_count

            # Determine spoke pattern offset
            if p.spoke_pattern == "radial":
                hub_theta = base_theta
                rim_theta = base_theta
            elif p.spoke_pattern == "2cross":
                # 2-cross pattern
                cross_angle = 2 * (2 * math.pi / p.spoke_count)
                hub_theta = base_theta + (cross_angle if i % 2 else -cross_angle)
                rim_theta = base_theta
            elif p.spoke_pattern == "3cross":
                # 3-cross pattern
                cross_angle = 3 * (2 * math.pi / p.spoke_count)
                hub_theta = base_theta + (cross_angle if i % 2 else -cross_angle)
                rim_theta = base_theta
            else:
                hub_theta = base_theta
                rim_theta = base_theta

            # Alternate sides (left/right flange)
            hub_x = hub_x_left if i % 2 == 0 else hub_x_right

            # Hub and rim attachment points
            hub_point = self._cylindrical_to_cartesian(hub_r, hub_theta, hub_x)
            rim_point = self._cylindrical_to_cartesian(rim_inner_r, rim_theta, hub_x * 0.3)

            # Generate spoke cylinder/blade
            self._generate_spoke_segment(hub_point, rim_point, p.spoke_profile)

    def _generate_spoke_segment(self, start: np.ndarray, end: np.ndarray, profile: str):
        """Generate a single spoke between two points."""
        p = self.params
        n_seg = p.spoke_segments

        # Direction vector
        direction = end - start
        length = np.linalg.norm(direction)
        direction = direction / length

        # Perpendicular vectors for spoke cross-section
        if abs(direction[2]) < 0.9:
            perp1 = np.cross(direction, np.array([0, 0, 1]))
        else:
            perp1 = np.cross(direction, np.array([1, 0, 0]))
        perp1 = perp1 / np.linalg.norm(perp1)
        perp2 = np.cross(direction, perp1)

        # Generate spoke as cylinder or blade
        for i in range(2):  # Start and end caps
            t = i  # 0 or 1 along spoke
            center = start + t * (end - start)

            for j in range(n_seg):
                theta1 = 2 * math.pi * j / n_seg
                theta2 = 2 * math.pi * (j + 1) / n_seg

                if profile == "round":
                    r = p.spoke_diameter / 2
                    offset1 = r * (math.cos(theta1) * perp1 + math.sin(theta1) * perp2)
                    offset2 = r * (math.cos(theta2) * perp1 + math.sin(theta2) * perp2)
                elif profile == "bladed":
                    # Elliptical cross-section
                    a = p.spoke_blade_width / 2
                    b = p.spoke_diameter / 2
                    offset1 = a * math.cos(theta1) * perp1 + b * math.sin(theta1) * perp2
                    offset2 = a * math.cos(theta2) * perp1 + b * math.sin(theta2) * perp2
                else:
                    r = p.spoke_diameter / 2
                    offset1 = r * (math.cos(theta1) * perp1 + math.sin(theta1) * perp2)
                    offset2 = r * (math.cos(theta2) * perp1 + math.sin(theta2) * perp2)

                if i == 0:
                    # Start cap
                    self.triangles.append((center, center + offset1, center + offset2))
                else:
                    # End cap
                    self.triangles.append((center, center + offset2, center + offset1))

        # Generate spoke sides
        for i in range(n_seg):
            theta1 = 2 * math.pi * i / n_seg
            theta2 = 2 * math.pi * (i + 1) / n_seg

            if profile == "round":
                r = p.spoke_diameter / 2
                off1 = r * (math.cos(theta1) * perp1 + math.sin(theta1) * perp2)
                off2 = r * (math.cos(theta2) * perp1 + math.sin(theta2) * perp2)
            elif profile == "bladed":
                a = p.spoke_blade_width / 2
                b = p.spoke_diameter / 2
                off1 = a * math.cos(theta1) * perp1 + b * math.sin(theta1) * perp2
                off2 = a * math.cos(theta2) * perp1 + b * math.sin(theta2) * perp2
            else:
                r = p.spoke_diameter / 2
                off1 = r * (math.cos(theta1) * perp1 + math.sin(theta1) * perp2)
                off2 = r * (math.cos(theta2) * perp1 + math.sin(theta2) * perp2)

            p1 = start + off1
            p2 = start + off2
            p3 = end + off2
            p4 = end + off1

            self.triangles.append((p1, p2, p3))
            self.triangles.append((p1, p3, p4))

    def _generate_hub(self):
        """Generate hub shell geometry."""
        p = self.params
        hub_r = p.hub_diameter / 2
        hub_x_left = -p.hub_width / 2
        hub_x_right = p.hub_width / 2

        n_circ = p.circumferential_segments

        # Hub cylinder
        for i in range(n_circ):
            theta1 = 2 * math.pi * i / n_circ
            theta2 = 2 * math.pi * (i + 1) / n_circ

            p1 = self._cylindrical_to_cartesian(hub_r, theta1, hub_x_left)
            p2 = self._cylindrical_to_cartesian(hub_r, theta2, hub_x_left)
            p3 = self._cylindrical_to_cartesian(hub_r, theta2, hub_x_right)
            p4 = self._cylindrical_to_cartesian(hub_r, theta1, hub_x_right)

            self.triangles.append((p1, p3, p2))
            self.triangles.append((p1, p4, p3))

        # Hub end caps
        center_left = np.array([hub_x_left, 0, 0])
        center_right = np.array([hub_x_right, 0, 0])

        for i in range(n_circ):
            theta1 = 2 * math.pi * i / n_circ
            theta2 = 2 * math.pi * (i + 1) / n_circ

            p1 = self._cylindrical_to_cartesian(hub_r, theta1, hub_x_left)
            p2 = self._cylindrical_to_cartesian(hub_r, theta2, hub_x_left)
            self.triangles.append((center_left, p2, p1))

            p3 = self._cylindrical_to_cartesian(hub_r, theta1, hub_x_right)
            p4 = self._cylindrical_to_cartesian(hub_r, theta2, hub_x_right)
            self.triangles.append((center_right, p3, p4))

    def _generate_spoke_fairing(self):
        """Generate fairing panels between spokes."""
        # Simplified: create disc sections between spokes
        pass  # TODO: Implement spoke fairing

    def _generate_disc(self):
        """Generate full disc wheel (no spokes visible)."""
        p = self.params
        hub_r = p.hub_diameter / 2
        rim_inner_r = p.outer_diameter / 2 - p.tire_height - p.rim_depth

        n_circ = p.circumferential_segments
        n_rad = 10  # Radial divisions

        # Generate disc on both sides
        for side in [-1, 1]:
            x_pos = side * p.hub_width / 4  # Slight offset

            for i in range(n_circ):
                theta1 = 2 * math.pi * i / n_circ
                theta2 = 2 * math.pi * (i + 1) / n_circ

                for j in range(n_rad):
                    r1 = hub_r + (rim_inner_r - hub_r) * j / n_rad
                    r2 = hub_r + (rim_inner_r - hub_r) * (j + 1) / n_rad

                    p1 = self._cylindrical_to_cartesian(r1, theta1, x_pos)
                    p2 = self._cylindrical_to_cartesian(r2, theta1, x_pos)
                    p3 = self._cylindrical_to_cartesian(r2, theta2, x_pos)
                    p4 = self._cylindrical_to_cartesian(r1, theta2, x_pos)

                    if side > 0:
                        self.triangles.append((p1, p2, p3))
                        self.triangles.append((p1, p3, p4))
                    else:
                        self.triangles.append((p1, p3, p2))
                        self.triangles.append((p1, p4, p3))

    def _cylindrical_to_cartesian(self, r: float, theta: float, x: float) -> np.ndarray:
        """
        Convert cylindrical coordinates to cartesian.
        Wheel axis is X, theta rotates in YZ plane.
        """
        return np.array([
            x,                    # Axle direction
            r * math.cos(theta),  # Forward direction
            r * math.sin(theta)   # Vertical
        ])

    def get_frontal_area(self) -> float:
        """Calculate projected frontal area (for Cd calculations)."""
        p = self.params

        # Approximate as ellipse (wheel + tire)
        height = p.outer_diameter
        width = max(p.rim_width_outer, p.tire_width) + p.hub_width

        # More accurate: project triangles onto YZ plane
        # For now, use simple approximation
        return math.pi * (height / 2) * (width / 2) * 0.9  # 0.9 factor for non-elliptical shape

    def save_stl(self, filepath: Path, binary: bool = True):
        """Save wheel geometry as STL file."""
        if not self.triangles:
            self.generate()

        filepath = Path(filepath)

        if binary:
            self._save_binary_stl(filepath)
        else:
            self._save_ascii_stl(filepath)

    def _save_binary_stl(self, filepath: Path):
        """Save as binary STL."""
        with open(filepath, 'wb') as f:
            # Header (80 bytes)
            header = b'WheelFlow Parametric Wheel Generator' + b'\0' * 43
            f.write(header[:80])

            # Number of triangles
            f.write(struct.pack('<I', len(self.triangles)))

            # Write triangles
            for p1, p2, p3 in self.triangles:
                # Calculate normal
                v1 = p2 - p1
                v2 = p3 - p1
                normal = np.cross(v1, v2)
                norm_length = np.linalg.norm(normal)
                if norm_length > 0:
                    normal = normal / norm_length
                else:
                    normal = np.array([0, 0, 1])

                # Write normal
                f.write(struct.pack('<3f', *normal))

                # Write vertices
                f.write(struct.pack('<3f', *p1))
                f.write(struct.pack('<3f', *p2))
                f.write(struct.pack('<3f', *p3))

                # Attribute byte count
                f.write(struct.pack('<H', 0))

    def _save_ascii_stl(self, filepath: Path):
        """Save as ASCII STL."""
        with open(filepath, 'w') as f:
            f.write("solid wheel\n")

            for p1, p2, p3 in self.triangles:
                # Calculate normal
                v1 = p2 - p1
                v2 = p3 - p1
                normal = np.cross(v1, v2)
                norm_length = np.linalg.norm(normal)
                if norm_length > 0:
                    normal = normal / norm_length
                else:
                    normal = np.array([0, 0, 1])

                f.write(f"  facet normal {normal[0]:.6e} {normal[1]:.6e} {normal[2]:.6e}\n")
                f.write("    outer loop\n")
                f.write(f"      vertex {p1[0]:.6e} {p1[1]:.6e} {p1[2]:.6e}\n")
                f.write(f"      vertex {p2[0]:.6e} {p2[1]:.6e} {p2[2]:.6e}\n")
                f.write(f"      vertex {p3[0]:.6e} {p3[1]:.6e} {p3[2]:.6e}\n")
                f.write("    endloop\n")
                f.write("  endfacet\n")

            f.write("endsolid wheel\n")

    def get_triangle_count(self) -> int:
        """Return number of triangles in mesh."""
        return len(self.triangles)

    def get_bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return bounding box (min, max) of geometry."""
        if not self.triangles:
            self.generate()

        all_points = []
        for p1, p2, p3 in self.triangles:
            all_points.extend([p1, p2, p3])

        points = np.array(all_points)
        return points.min(axis=0), points.max(axis=0)


def create_optimization_bounds() -> Dict[str, Tuple[float, float]]:
    """
    Define parameter bounds for optimization.
    Returns dict of (min, max) tuples for continuous parameters.
    """
    return {
        'rim_depth': (0.020, 0.100),           # 20-100mm
        'rim_width_outer': (0.020, 0.035),     # 20-35mm
        'rim_sidewall_curve': (0.0, 1.0),      # Straight to curved
        'spoke_count': (16, 36),               # Discrete
        'spoke_diameter': (0.0015, 0.003),     # 1.5-3mm
        'tire_width': (0.023, 0.032),          # 23-32mm
    }


def create_categorical_options() -> Dict[str, List[str]]:
    """Define categorical parameter options."""
    return {
        'rim_profile': ['toroidal', 'v_shape', 'box', 'aero'],
        'spoke_profile': ['round', 'bladed'],
        'spoke_pattern': ['radial', '2cross', '3cross'],
    }
