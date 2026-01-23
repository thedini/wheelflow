"""
AI-Driven Wheel Optimization Engine

Uses Bayesian optimization (Optuna) and genetic algorithms for
multi-objective aerodynamic optimization of bicycle wheels.
"""

import json
import logging
import math
import pickle
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import numpy as np

try:
    import optuna
    from optuna.samplers import TPESampler, NSGAIISampler, RandomSampler
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

from .parametric_wheel import (
    WheelParameters,
    ParametricWheel,
    create_optimization_bounds,
    create_categorical_options,
)

logger = logging.getLogger(__name__)


@dataclass
class OptimizationConfig:
    """Configuration for wheel optimization runs."""

    # Optimization algorithm
    algorithm: str = "bayesian"  # bayesian, nsga2, random
    n_trials: int = 50           # Number of optimization trials
    n_jobs: int = 1              # Parallel evaluations
    timeout: Optional[float] = None  # Max optimization time (seconds)

    # Objective weights (for single-objective mode)
    drag_weight: float = 1.0     # Weight for drag minimization
    side_force_weight: float = 0.3  # Weight for side force stability
    weight_proxy_weight: float = 0.1  # Weight for weight (rim depth proxy)

    # Multi-objective mode
    multi_objective: bool = False
    objectives: List[str] = field(default_factory=lambda: ['drag', 'side_force'])

    # CFD simulation settings
    flow_velocity: float = 13.9  # m/s (~50 km/h)
    yaw_angle: float = 15.0      # degrees
    air_density: float = 1.225   # kg/m³

    # Surrogate model settings
    use_surrogate: bool = True   # Use ML surrogate for fast evaluation
    surrogate_warmup: int = 10   # CFD runs before surrogate kicks in
    surrogate_confidence: float = 0.8  # Min confidence to skip CFD

    # Parameter constraints
    fixed_params: Dict[str, Any] = field(default_factory=dict)
    param_bounds: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    # Output settings
    output_dir: Optional[Path] = None
    save_all_geometries: bool = False
    checkpoint_interval: int = 10

    # Validation targets (AeroCloud reference)
    target_drag: float = 1.31    # N at 15° yaw
    target_side_force: float = 14.10  # N at 15° yaw

    def to_dict(self) -> Dict[str, Any]:
        """Serialize config to dictionary."""
        return {
            'algorithm': self.algorithm,
            'n_trials': self.n_trials,
            'n_jobs': self.n_jobs,
            'timeout': self.timeout,
            'drag_weight': self.drag_weight,
            'side_force_weight': self.side_force_weight,
            'weight_proxy_weight': self.weight_proxy_weight,
            'multi_objective': self.multi_objective,
            'objectives': self.objectives,
            'flow_velocity': self.flow_velocity,
            'yaw_angle': self.yaw_angle,
            'air_density': self.air_density,
            'use_surrogate': self.use_surrogate,
            'surrogate_warmup': self.surrogate_warmup,
            'target_drag': self.target_drag,
            'target_side_force': self.target_side_force,
        }


@dataclass
class OptimizationResult:
    """Result of a single optimization trial."""
    trial_id: int
    parameters: WheelParameters
    drag_force: float       # N
    side_force: float       # N
    lift_force: float       # N
    cd: float               # Drag coefficient
    cs: float               # Side force coefficient
    frontal_area: float     # m²
    cda: float              # Drag area (Cd * A)
    simulation_time: float  # seconds
    converged: bool
    used_surrogate: bool = False
    surrogate_confidence: float = 0.0

    def objective_value(self, config: OptimizationConfig) -> float:
        """Calculate weighted objective for single-objective optimization."""
        # Normalize forces to typical ranges
        drag_norm = self.drag_force / config.target_drag
        side_norm = abs(self.side_force) / config.target_side_force
        weight_norm = self.parameters.rim_depth / 0.050  # Normalize to 50mm

        return (
            config.drag_weight * drag_norm +
            config.side_force_weight * side_norm +
            config.weight_proxy_weight * weight_norm
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary."""
        return {
            'trial_id': self.trial_id,
            'parameters': self.parameters.to_dict(),
            'drag_force': self.drag_force,
            'side_force': self.side_force,
            'lift_force': self.lift_force,
            'cd': self.cd,
            'cs': self.cs,
            'frontal_area': self.frontal_area,
            'cda': self.cda,
            'simulation_time': self.simulation_time,
            'converged': self.converged,
            'used_surrogate': self.used_surrogate,
        }


class SurrogateModel:
    """
    Machine learning surrogate model for fast CFD predictions.

    Uses Gaussian Process Regression for uncertainty quantification,
    allowing intelligent decisions about when to run full CFD.
    """

    def __init__(self):
        self.model = None
        self.scaler_x = None
        self.scaler_y = None
        self.training_data: List[Tuple[np.ndarray, np.ndarray]] = []
        self.is_fitted = False

        # Try to import sklearn
        try:
            from sklearn.gaussian_process import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import RBF, ConstantKernel, Matern
            from sklearn.preprocessing import StandardScaler
            self.GP = GaussianProcessRegressor
            self.StandardScaler = StandardScaler
            self.kernel = ConstantKernel(1.0) * Matern(length_scale=1.0, nu=2.5)
            self.sklearn_available = True
        except ImportError:
            self.sklearn_available = False
            logger.warning("sklearn not available, surrogate model disabled")

    def add_sample(self, params: WheelParameters, result: OptimizationResult):
        """Add a CFD result to training data."""
        x = self._params_to_vector(params)
        y = np.array([result.drag_force, result.side_force])
        self.training_data.append((x, y))

        # Retrain if enough samples
        if len(self.training_data) >= 5:
            self._fit()

    def predict(self, params: WheelParameters) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict forces for given parameters.

        Returns:
            predictions: [drag, side_force] predictions
            std: [drag_std, side_std] standard deviations (uncertainty)
        """
        if not self.is_fitted or not self.sklearn_available:
            return np.array([1.0, 10.0]), np.array([1.0, 5.0])

        x = self._params_to_vector(params).reshape(1, -1)
        x_scaled = self.scaler_x.transform(x)

        pred, std = self.model.predict(x_scaled, return_std=True)
        pred = self.scaler_y.inverse_transform(pred.reshape(1, -1))[0]

        return pred, std

    def get_confidence(self, params: WheelParameters) -> float:
        """Get prediction confidence (0-1) for parameters."""
        if not self.is_fitted:
            return 0.0

        _, std = self.predict(params)
        # Confidence inversely proportional to uncertainty
        avg_std = np.mean(std)
        confidence = max(0, 1 - avg_std / 2)  # Normalize
        return float(confidence)

    def _params_to_vector(self, params: WheelParameters) -> np.ndarray:
        """Convert wheel parameters to feature vector."""
        # Numerical features
        features = [
            params.rim_depth,
            params.rim_width_outer,
            params.rim_sidewall_curve,
            params.spoke_count / 36,  # Normalize
            params.spoke_diameter,
            params.tire_width,
        ]

        # Encode categoricals
        rim_profiles = ['toroidal', 'v_shape', 'box', 'aero']
        spoke_profiles = ['round', 'bladed']
        spoke_patterns = ['radial', '2cross', '3cross']

        # One-hot encode rim profile
        for profile in rim_profiles:
            features.append(1.0 if params.rim_profile == profile else 0.0)

        # One-hot encode spoke profile
        for profile in spoke_profiles:
            features.append(1.0 if params.spoke_profile == profile else 0.0)

        # One-hot encode spoke pattern
        for pattern in spoke_patterns:
            features.append(1.0 if params.spoke_pattern == pattern else 0.0)

        return np.array(features)

    def _fit(self):
        """Fit the surrogate model on collected data."""
        if not self.sklearn_available or len(self.training_data) < 5:
            return

        X = np.array([x for x, y in self.training_data])
        Y = np.array([y for x, y in self.training_data])

        # Scale features
        self.scaler_x = self.StandardScaler()
        self.scaler_y = self.StandardScaler()

        X_scaled = self.scaler_x.fit_transform(X)
        Y_scaled = self.scaler_y.fit_transform(Y)

        # Fit GP model
        self.model = self.GP(kernel=self.kernel, n_restarts_optimizer=3)
        self.model.fit(X_scaled, Y_scaled)
        self.is_fitted = True

        logger.info(f"Surrogate model fitted on {len(self.training_data)} samples")

    def save(self, filepath: Path):
        """Save surrogate model to disk."""
        with open(filepath, 'wb') as f:
            pickle.dump({
                'training_data': self.training_data,
                'model': self.model,
                'scaler_x': self.scaler_x,
                'scaler_y': self.scaler_y,
                'is_fitted': self.is_fitted,
            }, f)

    def load(self, filepath: Path):
        """Load surrogate model from disk."""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
            self.training_data = data['training_data']
            self.model = data['model']
            self.scaler_x = data['scaler_x']
            self.scaler_y = data['scaler_y']
            self.is_fitted = data['is_fitted']


class WheelOptimizer:
    """
    AI-driven optimizer for bicycle wheel aerodynamics.

    Supports:
    - Bayesian optimization (TPE sampler) for efficient exploration
    - NSGA-II for multi-objective Pareto optimization
    - Random search baseline
    - Surrogate model acceleration
    """

    def __init__(
        self,
        config: OptimizationConfig,
        cfd_runner: Optional[Callable[[WheelParameters], OptimizationResult]] = None,
    ):
        self.config = config
        self.cfd_runner = cfd_runner or self._dummy_cfd_runner
        self.surrogate = SurrogateModel()
        self.results: List[OptimizationResult] = []
        self.study: Optional['optuna.Study'] = None
        self.best_result: Optional[OptimizationResult] = None

        # Setup bounds
        self.bounds = create_optimization_bounds()
        self.bounds.update(config.param_bounds)
        self.categoricals = create_categorical_options()

        # Apply fixed parameters
        for param, value in config.fixed_params.items():
            if param in self.bounds:
                del self.bounds[param]
            if param in self.categoricals:
                del self.categoricals[param]

    def optimize(self) -> List[OptimizationResult]:
        """
        Run optimization and return all results.

        Returns:
            List of OptimizationResult for all trials
        """
        if not OPTUNA_AVAILABLE:
            raise RuntimeError("Optuna not installed. Run: pip install optuna")

        # Create Optuna study
        if self.config.multi_objective:
            directions = ['minimize'] * len(self.config.objectives)
            sampler = NSGAIISampler(seed=42)
            self.study = optuna.create_study(
                directions=directions,
                sampler=sampler,
                study_name="wheel_optimization",
            )
        else:
            if self.config.algorithm == "bayesian":
                sampler = TPESampler(seed=42, n_startup_trials=10)
            elif self.config.algorithm == "random":
                sampler = RandomSampler(seed=42)
            else:
                sampler = TPESampler(seed=42)

            self.study = optuna.create_study(
                direction='minimize',
                sampler=sampler,
                study_name="wheel_optimization",
            )

        # Run optimization
        self.study.optimize(
            self._objective,
            n_trials=self.config.n_trials,
            n_jobs=self.config.n_jobs,
            timeout=self.config.timeout,
            callbacks=[self._trial_callback],
        )

        # Extract best result
        if self.config.multi_objective:
            # Return Pareto front
            pareto_trials = self.study.best_trials
            logger.info(f"Optimization complete. Pareto front size: {len(pareto_trials)}")
        else:
            best_trial = self.study.best_trial
            logger.info(
                f"Optimization complete. Best value: {best_trial.value:.4f}"
            )

        return self.results

    def _objective(self, trial: 'optuna.Trial') -> Union[float, Tuple[float, ...]]:
        """Optuna objective function."""
        # Sample parameters
        params = self._sample_parameters(trial)

        # Check surrogate model
        use_surrogate = False
        if (
            self.config.use_surrogate
            and len(self.results) >= self.config.surrogate_warmup
        ):
            confidence = self.surrogate.get_confidence(params)
            if confidence >= self.config.surrogate_confidence:
                use_surrogate = True

        # Evaluate
        start_time = time.time()

        if use_surrogate:
            result = self._evaluate_surrogate(trial.number, params)
        else:
            result = self._evaluate_cfd(trial.number, params)
            # Add to surrogate training data
            if self.config.use_surrogate:
                self.surrogate.add_sample(params, result)

        self.results.append(result)

        # Update best
        if self.best_result is None or result.drag_force < self.best_result.drag_force:
            self.best_result = result

        # Return objective(s)
        if self.config.multi_objective:
            objectives = []
            for obj_name in self.config.objectives:
                if obj_name == 'drag':
                    objectives.append(result.drag_force)
                elif obj_name == 'side_force':
                    objectives.append(abs(result.side_force))
                elif obj_name == 'weight':
                    objectives.append(params.rim_depth)
                elif obj_name == 'cda':
                    objectives.append(result.cda)
            return tuple(objectives)
        else:
            return result.objective_value(self.config)

    def _sample_parameters(self, trial: 'optuna.Trial') -> WheelParameters:
        """Sample wheel parameters from Optuna trial."""
        params_dict = {}

        # Continuous parameters
        for param_name, (low, high) in self.bounds.items():
            if param_name == 'spoke_count':
                # Integer parameter
                params_dict[param_name] = trial.suggest_int(param_name, int(low), int(high))
            else:
                params_dict[param_name] = trial.suggest_float(param_name, low, high)

        # Categorical parameters
        for param_name, options in self.categoricals.items():
            params_dict[param_name] = trial.suggest_categorical(param_name, options)

        # Apply fixed parameters
        params_dict.update(self.config.fixed_params)

        return WheelParameters(**params_dict)

    def _evaluate_cfd(self, trial_id: int, params: WheelParameters) -> OptimizationResult:
        """Run full CFD simulation."""
        return self.cfd_runner(params)

    def _evaluate_surrogate(
        self, trial_id: int, params: WheelParameters
    ) -> OptimizationResult:
        """Use surrogate model for fast evaluation."""
        pred, std = self.surrogate.predict(params)
        confidence = self.surrogate.get_confidence(params)

        # Generate geometry for frontal area
        wheel = ParametricWheel(params)
        frontal_area = wheel.get_frontal_area()

        # Calculate coefficients
        q = 0.5 * self.config.air_density * self.config.flow_velocity ** 2
        cd = pred[0] / (q * frontal_area) if frontal_area > 0 else 0
        cs = pred[1] / (q * frontal_area) if frontal_area > 0 else 0

        return OptimizationResult(
            trial_id=trial_id,
            parameters=params,
            drag_force=float(pred[0]),
            side_force=float(pred[1]),
            lift_force=0.0,
            cd=cd,
            cs=cs,
            frontal_area=frontal_area,
            cda=cd * frontal_area,
            simulation_time=0.01,
            converged=True,
            used_surrogate=True,
            surrogate_confidence=confidence,
        )

    def _dummy_cfd_runner(self, params: WheelParameters) -> OptimizationResult:
        """
        Dummy CFD runner for testing.
        Uses physics-based approximations.
        """
        # Generate geometry
        wheel = ParametricWheel(params)
        frontal_area = wheel.get_frontal_area()

        # Physics-based drag model
        # Base Cd depends on rim profile
        base_cd = {
            'toroidal': 0.45,
            'v_shape': 0.50,
            'box': 0.65,
            'aero': 0.40,
        }.get(params.rim_profile, 0.50)

        # Rim depth effect (deeper = less drag at yaw)
        depth_factor = 1.0 - 0.3 * (params.rim_depth - 0.030) / 0.050

        # Spoke drag contribution
        spoke_cd_contribution = params.spoke_count * 0.001
        if params.spoke_profile == 'bladed':
            spoke_cd_contribution *= 0.7

        # Total Cd
        cd = base_cd * depth_factor + spoke_cd_contribution

        # Calculate forces
        q = 0.5 * self.config.air_density * self.config.flow_velocity ** 2
        yaw_rad = math.radians(self.config.yaw_angle)

        # Drag and side force at yaw
        drag_force = cd * q * frontal_area * math.cos(yaw_rad)
        side_force = cd * q * frontal_area * 3.5 * math.sin(yaw_rad)  # Side force ~3.5x drag at yaw

        # Add some noise to simulate CFD variability
        drag_force *= 1.0 + 0.02 * (np.random.random() - 0.5)
        side_force *= 1.0 + 0.05 * (np.random.random() - 0.5)

        return OptimizationResult(
            trial_id=0,
            parameters=params,
            drag_force=drag_force,
            side_force=side_force,
            lift_force=0.1 * drag_force,
            cd=cd,
            cs=side_force / (q * frontal_area),
            frontal_area=frontal_area,
            cda=cd * frontal_area,
            simulation_time=0.5 + np.random.random(),
            converged=True,
            used_surrogate=False,
        )

    def _trial_callback(self, study: 'optuna.Study', trial: 'optuna.FrozenTrial'):
        """Callback after each trial."""
        if trial.number % self.config.checkpoint_interval == 0:
            self._save_checkpoint()

        # Log progress
        if self.config.multi_objective:
            logger.info(
                f"Trial {trial.number}: values={trial.values}"
            )
        else:
            logger.info(
                f"Trial {trial.number}: value={trial.value:.4f}, "
                f"best={study.best_value:.4f}"
            )

    def _save_checkpoint(self):
        """Save optimization checkpoint."""
        if self.config.output_dir is None:
            return

        checkpoint_dir = self.config.output_dir / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Save results
        results_file = checkpoint_dir / "results.json"
        with open(results_file, 'w') as f:
            json.dump([r.to_dict() for r in self.results], f, indent=2)

        # Save surrogate model
        if self.surrogate.is_fitted:
            surrogate_file = checkpoint_dir / "surrogate.pkl"
            self.surrogate.save(surrogate_file)

        logger.info(f"Checkpoint saved to {checkpoint_dir}")

    def get_pareto_front(self) -> List[OptimizationResult]:
        """Get Pareto-optimal solutions for multi-objective optimization."""
        if not self.config.multi_objective or self.study is None:
            return [self.best_result] if self.best_result else []

        pareto_results = []
        for trial in self.study.best_trials:
            # Find corresponding result
            if trial.number < len(self.results):
                pareto_results.append(self.results[trial.number])

        return pareto_results

    def get_optimization_history(self) -> Dict[str, List[float]]:
        """Get optimization history for visualization."""
        history = {
            'trial': [],
            'drag_force': [],
            'side_force': [],
            'objective': [],
            'best_objective': [],
        }

        best_obj = float('inf')
        for result in self.results:
            history['trial'].append(result.trial_id)
            history['drag_force'].append(result.drag_force)
            history['side_force'].append(result.side_force)

            obj = result.objective_value(self.config)
            history['objective'].append(obj)

            best_obj = min(best_obj, obj)
            history['best_objective'].append(best_obj)

        return history

    def suggest_next_experiment(self) -> WheelParameters:
        """
        Suggest parameters for the next CFD experiment.
        Useful for human-in-the-loop optimization.
        """
        if self.study is None:
            # Return default parameters
            return WheelParameters.deep_section()

        # Ask Optuna for next suggestion
        trial = self.study.ask()
        params = self._sample_parameters(trial)

        return params

    def report_experiment_result(
        self,
        params: WheelParameters,
        drag_force: float,
        side_force: float,
        lift_force: float = 0.0,
    ):
        """
        Report results from external CFD experiment.
        Useful for human-in-the-loop optimization.
        """
        wheel = ParametricWheel(params)
        frontal_area = wheel.get_frontal_area()

        q = 0.5 * self.config.air_density * self.config.flow_velocity ** 2
        cd = drag_force / (q * frontal_area) if frontal_area > 0 else 0
        cs = side_force / (q * frontal_area) if frontal_area > 0 else 0

        result = OptimizationResult(
            trial_id=len(self.results),
            parameters=params,
            drag_force=drag_force,
            side_force=side_force,
            lift_force=lift_force,
            cd=cd,
            cs=cs,
            frontal_area=frontal_area,
            cda=cd * frontal_area,
            simulation_time=0.0,
            converged=True,
        )

        self.results.append(result)
        self.surrogate.add_sample(params, result)

        # Update best
        if self.best_result is None or drag_force < self.best_result.drag_force:
            self.best_result = result


def create_cfd_runner(
    wheelflow_backend: Any,
    output_dir: Path,
    mesh_quality: str = "standard",
) -> Callable[[WheelParameters], OptimizationResult]:
    """
    Create a CFD runner function that integrates with WheelFlow backend.

    Args:
        wheelflow_backend: Reference to WheelFlow app backend
        output_dir: Directory for simulation cases
        mesh_quality: Mesh quality preset (basic, standard, pro)

    Returns:
        Callable that runs CFD for given parameters
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    executor = ThreadPoolExecutor(max_workers=1)

    def runner(params: WheelParameters) -> OptimizationResult:
        # Generate wheel STL
        wheel = ParametricWheel(params)
        wheel.generate()

        stl_path = output_dir / f"wheel_{id(params)}.stl"
        wheel.save_stl(stl_path)

        # Run CFD simulation through WheelFlow
        # This would integrate with the existing backend
        # For now, use dummy runner
        return WheelOptimizer(OptimizationConfig())._dummy_cfd_runner(params)

    return runner
