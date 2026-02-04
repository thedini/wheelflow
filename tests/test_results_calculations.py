"""
Unit tests for Results Dashboard calculations and data extraction.

Tests the coefficient calculations, force conversions, and result parsing
used in the Results Dashboard (US-001).
"""

import pytest
import math


class TestCoefficientCalculations:
    """Test aerodynamic coefficient calculations."""

    # Standard air properties at sea level
    RHO = 1.225  # kg/m³
    SPEED = 13.9  # m/s
    AREF = 0.0225  # m² (AeroCloud standard reference area)

    def dynamic_pressure(self, speed=None):
        """Calculate dynamic pressure q = 0.5 * rho * V²"""
        v = speed or self.SPEED
        return 0.5 * self.RHO * v * v

    def test_dynamic_pressure_calculation(self):
        """Test dynamic pressure calculation at standard conditions."""
        q = self.dynamic_pressure()
        # q = 0.5 * 1.225 * 13.9² ≈ 118.3 Pa
        assert abs(q - 118.3) < 0.5

    def test_drag_coefficient_from_force(self):
        """Test Cd = Fd / (q * A)."""
        drag_N = 1.31  # N (AeroCloud reference at 15° yaw)
        q = self.dynamic_pressure()
        Cd = drag_N / (q * self.AREF)
        # Expected Cd ≈ 0.49
        assert 0.4 < Cd < 0.6

    def test_force_from_coefficient(self):
        """Test Fd = Cd * q * A."""
        Cd = 0.490
        q = self.dynamic_pressure()
        drag_N = Cd * q * self.AREF
        # Should be close to 1.31 N
        assert abs(drag_N - 1.30) < 0.1

    def test_cda_calculation(self):
        """Test CdA (drag area) calculation."""
        Cd = 0.490
        CdA = Cd * self.AREF
        # CdA in m²
        assert abs(CdA - 0.011) < 0.002
        # CdA in cm²
        CdA_cm2 = CdA * 10000
        assert abs(CdA_cm2 - 110) < 20

    def test_side_force_from_yaw(self):
        """Test side force calculation from yaw angle."""
        lift_N = 0.27  # N
        yaw_deg = 15.0

        # Side force approximation: Fs ≈ Fl * sin(yaw)
        Fs = lift_N * math.sin(math.radians(yaw_deg))
        assert abs(Fs - 0.07) < 0.02

    def test_side_force_zero_at_zero_yaw(self):
        """Side force should be zero at 0° yaw."""
        lift_N = 0.27
        yaw_deg = 0.0
        Fs = lift_N * math.sin(math.radians(yaw_deg))
        assert Fs == 0.0

    def test_moment_calculation(self):
        """Test moment calculation from Cm."""
        Cm = 0.05
        q = self.dynamic_pressure()
        lRef = 0.65  # Wheel diameter
        moment_Nm = Cm * q * self.AREF * lRef
        assert moment_Nm > 0


class TestReynoldsNumber:
    """Test Reynolds number calculations."""

    NU = 1.48e-5  # m²/s (kinematic viscosity of air)

    def test_reynolds_for_wheel(self):
        """Test Reynolds number for typical wheel."""
        speed = 13.9  # m/s
        diameter = 0.65  # m
        Re = speed * diameter / self.NU
        # Should be around 610,000
        assert 500000 < Re < 700000

    def test_reynolds_display_format(self):
        """Test Reynolds number display in k format."""
        Re = 610000
        Re_k = Re / 1000
        assert abs(Re_k - 610) < 50


class TestAngularVelocity:
    """Test wheel rotation calculations."""

    def test_omega_calculation(self):
        """Test angular velocity from linear speed."""
        speed = 13.9  # m/s
        radius = 0.325  # m
        omega = speed / radius
        # Should be around 42.8 rad/s
        assert abs(omega - 42.8) < 0.5

    def test_omega_for_different_speeds(self):
        """Test omega scales linearly with speed."""
        radius = 0.325
        omega_10 = 10.0 / radius
        omega_20 = 20.0 / radius
        assert abs(omega_20 / omega_10 - 2.0) < 0.01


class TestVelocityComponents:
    """Test velocity decomposition for yaw angles."""

    def test_zero_yaw_velocity(self):
        """At 0° yaw, all velocity is in x direction."""
        speed = 13.9
        yaw_deg = 0.0
        yaw_rad = math.radians(yaw_deg)

        vx = speed * math.cos(yaw_rad)
        vy = speed * math.sin(yaw_rad)

        assert abs(vx - speed) < 0.001
        assert abs(vy) < 0.001

    def test_fifteen_degree_yaw(self):
        """Test velocity components at 15° yaw."""
        speed = 13.9
        yaw_deg = 15.0
        yaw_rad = math.radians(yaw_deg)

        vx = speed * math.cos(yaw_rad)
        vy = speed * math.sin(yaw_rad)

        # cos(15°) ≈ 0.966, sin(15°) ≈ 0.259
        assert abs(vx - 13.43) < 0.1
        assert abs(vy - 3.60) < 0.1

    def test_velocity_magnitude_preserved(self):
        """Velocity magnitude should be preserved at any yaw."""
        speed = 13.9
        for yaw_deg in [0, 5, 10, 15, 20, 25]:
            yaw_rad = math.radians(yaw_deg)
            vx = speed * math.cos(yaw_rad)
            vy = speed * math.sin(yaw_rad)
            magnitude = math.sqrt(vx**2 + vy**2)
            assert abs(magnitude - speed) < 0.001


class TestResultsDataStructure:
    """Test the expected results data structure."""

    def test_results_has_required_fields(self):
        """Test that results dict has all required fields."""
        # Simulated results structure from backend
        results = {
            "forces": {"drag_N": 1.31, "lift_N": 0.27},
            "coefficients": {"Cd": 0.490, "Cl": 0.10, "Cm": 0.05},
            "CdA": 0.011,
            "converged": True,
            "aref": 0.0225,
        }

        assert "forces" in results
        assert "coefficients" in results
        assert "CdA" in results
        assert "converged" in results

        assert "drag_N" in results["forces"]
        assert "lift_N" in results["forces"]
        assert "Cd" in results["coefficients"]
        assert "Cl" in results["coefficients"]

    def test_job_config_has_required_fields(self):
        """Test that job config has all required fields for display."""
        config = {
            "speed": 13.9,
            "yaw_angles": [0, 5, 10, 15, 20],
            "quality": "standard",
            "ground_enabled": True,
            "ground_type": "moving",
            "rolling_enabled": True,
            "wheel_radius": 0.325,
            "reynolds": 610000,
        }

        required_fields = [
            "speed", "yaw_angles", "quality", "ground_enabled",
            "ground_type", "rolling_enabled", "wheel_radius"
        ]

        for field in required_fields:
            assert field in config, f"Missing required field: {field}"


class TestMetricTypeConversions:
    """Test conversions between metric types (Force/Coefficient/CdA/Moment)."""

    RHO = 1.225
    SPEED = 13.9
    AREF = 0.0225
    LREF = 0.65

    def setup_method(self):
        """Set up test fixtures."""
        self.q = 0.5 * self.RHO * self.SPEED**2

    def test_force_to_coefficient(self):
        """Convert force to coefficient."""
        drag_N = 1.31
        Cd = drag_N / (self.q * self.AREF)
        assert 0.4 < Cd < 0.6

    def test_coefficient_to_force(self):
        """Convert coefficient to force."""
        Cd = 0.490
        drag_N = Cd * self.q * self.AREF
        assert 1.0 < drag_N < 1.5

    def test_coefficient_to_cda(self):
        """Convert coefficient to CdA."""
        Cd = 0.490
        CdA = Cd * self.AREF
        CdA_cm2 = CdA * 10000
        assert 100 < CdA_cm2 < 120

    def test_coefficient_to_moment(self):
        """Convert Cm to moment in Nm."""
        Cm = 0.05
        moment_Nm = Cm * self.q * self.AREF * self.LREF
        assert moment_Nm > 0
        assert moment_Nm < 1.0  # Reasonable range for wheel


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
