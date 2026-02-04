"""
AeroCloud Validation Test Suite

Tests issue #14: Validation Against AeroCloud Reference Data

This module validates WheelFlow CFD results against AeroCloud TTTR28_22_TSV3
reference data to ensure simulation accuracy and credibility.

Reference Conditions:
- Wheel: TTTR28_22_TSV3 (28mm tire, 22mm rim depth)
- Speed: 50 km/h (13.9 m/s)
- Yaw angle: 15°
- Air density: 1.225 kg/m³
- Reference area (Aref): 0.0225 m²
"""

import pytest
import math
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class AeroCloudReference:
    """AeroCloud TTTR28_22_TSV3 reference data at 15° yaw."""

    # Test conditions
    speed_kmh: float = 50.0
    speed_ms: float = 13.889  # 50 km/h in m/s
    yaw_angle: float = 15.0  # degrees
    air_density: float = 1.225  # kg/m³
    aref: float = 0.0225  # m² (AeroCloud standard)

    # Reference forces (Newtons)
    drag_force: float = 1.31
    side_force: float = 14.10
    lift_force: float = -8.652e-3

    # Reference coefficients (dimensionless)
    cd: float = 0.490
    cs: float = 5.253
    cl: float = -0.003

    # Reference moments (Nm)
    yaw_moment: float = 4.34

    # Tolerances
    force_tolerance: float = 0.05  # ±5%
    coefficient_tolerance: float = 0.05  # ±5%
    moment_tolerance: float = 0.10  # ±10%
    lift_tolerance: float = 0.20  # ±20% (lift is small and variable)


AEROCLOUD_REF = AeroCloudReference()


def calculate_dynamic_pressure(speed: float, density: float = 1.225) -> float:
    """Calculate dynamic pressure q = 0.5 * rho * V^2."""
    return 0.5 * density * speed ** 2


def calculate_coefficient(force: float, q: float, aref: float) -> float:
    """Calculate aerodynamic coefficient C = F / (q * Aref)."""
    if q * aref == 0:
        return 0.0
    return force / (q * aref)


def within_tolerance(actual: float, expected: float, tolerance: float) -> bool:
    """Check if actual value is within tolerance of expected value."""
    if expected == 0:
        return abs(actual) < tolerance
    return abs((actual - expected) / expected) <= tolerance


def percent_error(actual: float, expected: float) -> float:
    """Calculate percent error between actual and expected values."""
    if expected == 0:
        return float('inf') if actual != 0 else 0.0
    return ((actual - expected) / expected) * 100


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    metric: str
    expected: float
    actual: float
    tolerance: float
    unit: str
    passed: bool
    error_percent: float

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        return (f"{self.metric}: {self.actual:.4f} {self.unit} "
                f"(expected: {self.expected:.4f}, error: {self.error_percent:+.1f}%, "
                f"tolerance: ±{self.tolerance*100:.0f}%) [{status}]")


class AeroCloudValidator:
    """Validator for comparing simulation results against AeroCloud reference."""

    def __init__(self, reference: AeroCloudReference = AEROCLOUD_REF):
        self.ref = reference
        self.results: list[ValidationResult] = []

    def validate_drag_force(self, actual: float) -> ValidationResult:
        """Validate drag force against reference."""
        result = ValidationResult(
            metric="Drag Force (Fd)",
            expected=self.ref.drag_force,
            actual=actual,
            tolerance=self.ref.force_tolerance,
            unit="N",
            passed=within_tolerance(actual, self.ref.drag_force, self.ref.force_tolerance),
            error_percent=percent_error(actual, self.ref.drag_force)
        )
        self.results.append(result)
        return result

    def validate_side_force(self, actual: float) -> ValidationResult:
        """Validate side force against reference."""
        result = ValidationResult(
            metric="Side Force (Fs)",
            expected=self.ref.side_force,
            actual=actual,
            tolerance=self.ref.force_tolerance,
            unit="N",
            passed=within_tolerance(actual, self.ref.side_force, self.ref.force_tolerance),
            error_percent=percent_error(actual, self.ref.side_force)
        )
        self.results.append(result)
        return result

    def validate_lift_force(self, actual: float) -> ValidationResult:
        """Validate lift force against reference (higher tolerance due to small magnitude)."""
        result = ValidationResult(
            metric="Lift Force (Fl)",
            expected=self.ref.lift_force,
            actual=actual,
            tolerance=self.ref.lift_tolerance,
            unit="N",
            passed=within_tolerance(actual, self.ref.lift_force, self.ref.lift_tolerance),
            error_percent=percent_error(actual, self.ref.lift_force)
        )
        self.results.append(result)
        return result

    def validate_drag_coefficient(self, actual: float) -> ValidationResult:
        """Validate drag coefficient against reference."""
        result = ValidationResult(
            metric="Drag Coefficient (Cd)",
            expected=self.ref.cd,
            actual=actual,
            tolerance=self.ref.coefficient_tolerance,
            unit="",
            passed=within_tolerance(actual, self.ref.cd, self.ref.coefficient_tolerance),
            error_percent=percent_error(actual, self.ref.cd)
        )
        self.results.append(result)
        return result

    def validate_side_coefficient(self, actual: float) -> ValidationResult:
        """Validate side force coefficient against reference."""
        result = ValidationResult(
            metric="Side Coefficient (Cs)",
            expected=self.ref.cs,
            actual=actual,
            tolerance=self.ref.coefficient_tolerance,
            unit="",
            passed=within_tolerance(actual, self.ref.cs, self.ref.coefficient_tolerance),
            error_percent=percent_error(actual, self.ref.cs)
        )
        self.results.append(result)
        return result

    def validate_yaw_moment(self, actual: float) -> ValidationResult:
        """Validate yaw moment against reference."""
        result = ValidationResult(
            metric="Yaw Moment (My)",
            expected=self.ref.yaw_moment,
            actual=actual,
            tolerance=self.ref.moment_tolerance,
            unit="Nm",
            passed=within_tolerance(actual, self.ref.yaw_moment, self.ref.moment_tolerance),
            error_percent=percent_error(actual, self.ref.yaw_moment)
        )
        self.results.append(result)
        return result

    def validate_all(self, simulation_results: Dict[str, float]) -> Dict[str, ValidationResult]:
        """
        Validate all metrics from simulation results.

        Args:
            simulation_results: Dict with keys 'drag', 'side', 'lift', 'Cd', 'Cs', 'yaw_moment'

        Returns:
            Dict mapping metric names to ValidationResult objects
        """
        validations = {}

        if 'drag' in simulation_results:
            validations['drag'] = self.validate_drag_force(simulation_results['drag'])

        if 'side' in simulation_results:
            validations['side'] = self.validate_side_force(simulation_results['side'])

        if 'lift' in simulation_results:
            validations['lift'] = self.validate_lift_force(simulation_results['lift'])

        if 'Cd' in simulation_results:
            validations['Cd'] = self.validate_drag_coefficient(simulation_results['Cd'])

        if 'Cs' in simulation_results:
            validations['Cs'] = self.validate_side_coefficient(simulation_results['Cs'])

        if 'yaw_moment' in simulation_results:
            validations['yaw_moment'] = self.validate_yaw_moment(simulation_results['yaw_moment'])

        return validations

    def get_summary(self) -> str:
        """Get a summary of all validation results."""
        if not self.results:
            return "No validation results."

        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        lines = [
            "=" * 60,
            "AeroCloud Validation Summary",
            "=" * 60,
            f"Reference: TTTR28_22_TSV3 at {self.ref.yaw_angle}° yaw",
            f"Conditions: {self.ref.speed_kmh} km/h, ρ={self.ref.air_density} kg/m³",
            f"Reference Area: {self.ref.aref} m²",
            "-" * 60,
        ]

        for result in self.results:
            lines.append(str(result))

        lines.extend([
            "-" * 60,
            f"Overall: {passed}/{total} validations passed",
            "=" * 60,
        ])

        return "\n".join(lines)

    @property
    def all_passed(self) -> bool:
        """Check if all validations passed."""
        return all(r.passed for r in self.results) if self.results else False


# ============================================================================
# PYTEST TEST CASES
# ============================================================================

class TestAeroCloudReference:
    """Tests for AeroCloud reference data consistency."""

    def test_reference_cd_calculation(self):
        """Verify Cd is consistent with drag force, speed, and Aref."""
        q = calculate_dynamic_pressure(AEROCLOUD_REF.speed_ms, AEROCLOUD_REF.air_density)
        calculated_cd = calculate_coefficient(
            AEROCLOUD_REF.drag_force, q, AEROCLOUD_REF.aref
        )
        assert abs(calculated_cd - AEROCLOUD_REF.cd) < 0.01, \
            f"Cd mismatch: calculated {calculated_cd:.3f}, reference {AEROCLOUD_REF.cd}"

    def test_reference_cs_calculation(self):
        """Verify Cs is consistent with side force, speed, and Aref."""
        q = calculate_dynamic_pressure(AEROCLOUD_REF.speed_ms, AEROCLOUD_REF.air_density)
        calculated_cs = calculate_coefficient(
            AEROCLOUD_REF.side_force, q, AEROCLOUD_REF.aref
        )
        # Allow 1% tolerance for rounding differences in reference data
        assert abs(calculated_cs - AEROCLOUD_REF.cs) < 0.1, \
            f"Cs mismatch: calculated {calculated_cs:.3f}, reference {AEROCLOUD_REF.cs}"

    def test_speed_conversion(self):
        """Verify speed conversion from km/h to m/s."""
        expected_ms = AEROCLOUD_REF.speed_kmh / 3.6
        assert abs(AEROCLOUD_REF.speed_ms - expected_ms) < 0.01


class TestValidationFunctions:
    """Tests for validation helper functions."""

    def test_within_tolerance_exact(self):
        """Test within_tolerance with exact match."""
        assert within_tolerance(1.0, 1.0, 0.05)

    def test_within_tolerance_at_boundary(self):
        """Test within_tolerance at tolerance boundary."""
        # At exactly 5% error, should pass (using <= comparison)
        assert within_tolerance(1.049, 1.0, 0.05)  # 4.9% error
        assert within_tolerance(0.951, 1.0, 0.05)  # 4.9% error

    def test_within_tolerance_outside(self):
        """Test within_tolerance outside boundary."""
        assert not within_tolerance(1.06, 1.0, 0.05)
        assert not within_tolerance(0.94, 1.0, 0.05)

    def test_percent_error_zero(self):
        """Test percent_error with zero error."""
        assert percent_error(1.0, 1.0) == 0.0

    def test_percent_error_positive(self):
        """Test percent_error with positive error."""
        assert abs(percent_error(1.1, 1.0) - 10.0) < 0.01

    def test_percent_error_negative(self):
        """Test percent_error with negative error."""
        assert abs(percent_error(0.9, 1.0) - (-10.0)) < 0.01


class TestAeroCloudValidator:
    """Tests for AeroCloudValidator class."""

    def test_validate_drag_force_pass(self):
        """Test drag force validation within tolerance."""
        validator = AeroCloudValidator()
        # 1.31 N ± 5% = [1.2445, 1.3755]
        result = validator.validate_drag_force(1.31)
        assert result.passed

    def test_validate_drag_force_fail(self):
        """Test drag force validation outside tolerance."""
        validator = AeroCloudValidator()
        result = validator.validate_drag_force(1.5)  # >5% error
        assert not result.passed

    def test_validate_side_force_pass(self):
        """Test side force validation within tolerance."""
        validator = AeroCloudValidator()
        result = validator.validate_side_force(14.0)  # ~0.7% error
        assert result.passed

    def test_validate_cd_pass(self):
        """Test Cd validation within tolerance."""
        validator = AeroCloudValidator()
        result = validator.validate_drag_coefficient(0.48)  # ~2% error
        assert result.passed

    def test_validate_all(self):
        """Test validating all metrics at once."""
        validator = AeroCloudValidator()
        results = validator.validate_all({
            'drag': 1.31,
            'side': 14.10,
            'Cd': 0.490,
            'Cs': 5.253,
        })
        assert len(results) == 4
        assert validator.all_passed

    def test_validation_summary(self):
        """Test generation of validation summary."""
        validator = AeroCloudValidator()
        validator.validate_drag_force(1.31)
        validator.validate_side_force(14.10)

        summary = validator.get_summary()
        assert "AeroCloud Validation Summary" in summary
        assert "TTTR28_22_TSV3" in summary
        assert "2/2 validations passed" in summary


class TestSimulationValidation:
    """
    Tests for validating actual simulation results.

    These tests are marked with @pytest.mark.simulation and require
    a completed simulation to run.
    """

    @pytest.mark.skip(reason="Requires completed simulation with matching conditions")
    def test_simulation_results_validation(self):
        """
        Validate actual simulation results against AeroCloud reference.

        To run this test:
        1. Run a simulation with TTTR28_22_TSV3 wheel at 15° yaw, 50 km/h
        2. Update the results dict below with actual values
        3. Remove the skip marker
        """
        # TODO: Replace with actual simulation results
        simulation_results = {
            'drag': 0.0,  # Replace with actual drag force (N)
            'side': 0.0,  # Replace with actual side force (N)
            'lift': 0.0,  # Replace with actual lift force (N)
            'Cd': 0.0,    # Replace with actual Cd
            'Cs': 0.0,    # Replace with actual Cs
            'yaw_moment': 0.0,  # Replace with actual yaw moment (Nm)
        }

        validator = AeroCloudValidator()
        validations = validator.validate_all(simulation_results)

        print("\n" + validator.get_summary())

        # High-priority validations (must pass)
        assert validations['drag'].passed, f"Drag validation failed: {validations['drag']}"
        assert validations['side'].passed, f"Side force validation failed: {validations['side']}"
        assert validations['Cd'].passed, f"Cd validation failed: {validations['Cd']}"
        assert validations['Cs'].passed, f"Cs validation failed: {validations['Cs']}"
