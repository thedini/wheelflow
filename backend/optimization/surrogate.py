"""
Advanced Surrogate Models for CFD Prediction

Provides multiple surrogate modeling approaches:
- Gaussian Process (GP) for small datasets with uncertainty
- Neural Network for larger datasets
- Ensemble methods combining both
"""

import json
import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """Extract and normalize features from wheel parameters."""

    # Define feature specifications
    NUMERICAL_FEATURES = [
        ('rim_depth', 0.020, 0.100),
        ('rim_width_outer', 0.020, 0.035),
        ('rim_width_inner', 0.015, 0.025),
        ('rim_sidewall_curve', 0.0, 1.0),
        ('tire_width', 0.023, 0.032),
        ('tire_height', 0.020, 0.035),
        ('spoke_count', 0, 36),
        ('spoke_diameter', 0.001, 0.004),
        ('spoke_blade_width', 0.002, 0.006),
    ]

    CATEGORICAL_FEATURES = {
        'rim_profile': ['toroidal', 'v_shape', 'box', 'aero'],
        'tire_profile': ['round', 'semi_slick', 'tubular'],
        'spoke_profile': ['round', 'bladed', 'aero'],
        'spoke_pattern': ['radial', '2cross', '3cross', 'paired'],
    }

    def __init__(self):
        self.feature_dim = (
            len(self.NUMERICAL_FEATURES) +
            sum(len(opts) for opts in self.CATEGORICAL_FEATURES.values())
        )

    def extract(self, params: Any) -> np.ndarray:
        """Extract feature vector from WheelParameters."""
        features = []

        # Numerical features (normalized to 0-1)
        for name, min_val, max_val in self.NUMERICAL_FEATURES:
            value = getattr(params, name, (min_val + max_val) / 2)
            if max_val > min_val:
                normalized = (value - min_val) / (max_val - min_val)
            else:
                normalized = 0.5
            features.append(np.clip(normalized, 0, 1))

        # Categorical features (one-hot encoded)
        for name, options in self.CATEGORICAL_FEATURES.items():
            value = getattr(params, name, options[0])
            for option in options:
                features.append(1.0 if value == option else 0.0)

        return np.array(features, dtype=np.float32)

    def extract_batch(self, params_list: List[Any]) -> np.ndarray:
        """Extract features for multiple parameter sets."""
        return np.array([self.extract(p) for p in params_list])


class GPSurrogate:
    """
    Gaussian Process surrogate model with uncertainty quantification.

    Best for:
    - Small datasets (<100 samples)
    - When uncertainty estimates are needed
    - Bayesian optimization integration
    """

    def __init__(self, kernel: str = "matern"):
        self.feature_extractor = FeatureExtractor()
        self.model = None
        self.scaler_y = None
        self.is_fitted = False
        self.kernel_type = kernel

        try:
            from sklearn.gaussian_process import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import (
                RBF, ConstantKernel, Matern, WhiteKernel
            )
            from sklearn.preprocessing import StandardScaler
            from sklearn.multioutput import MultiOutputRegressor

            # Build kernel
            if kernel == "matern":
                base_kernel = ConstantKernel(1.0) * Matern(
                    length_scale=np.ones(self.feature_extractor.feature_dim),
                    nu=2.5
                )
            else:
                base_kernel = ConstantKernel(1.0) * RBF(
                    length_scale=np.ones(self.feature_extractor.feature_dim)
                )

            # Add noise kernel
            self.kernel = base_kernel + WhiteKernel(noise_level=0.1)

            self.GP = GaussianProcessRegressor
            self.StandardScaler = StandardScaler
            self.MultiOutput = MultiOutputRegressor
            self.sklearn_available = True

        except ImportError:
            self.sklearn_available = False
            logger.warning("sklearn not available for GP surrogate")

    def fit(self, params_list: List[Any], results: np.ndarray):
        """
        Fit GP model on training data.

        Args:
            params_list: List of WheelParameters
            results: Array of shape (n_samples, n_outputs) with [drag, side_force, ...]
        """
        if not self.sklearn_available:
            logger.error("Cannot fit GP: sklearn not available")
            return

        X = self.feature_extractor.extract_batch(params_list)
        Y = np.array(results)

        # Scale outputs
        self.scaler_y = self.StandardScaler()
        Y_scaled = self.scaler_y.fit_transform(Y)

        # Fit multi-output GP
        base_gp = self.GP(
            kernel=self.kernel,
            n_restarts_optimizer=5,
            normalize_y=False,
            random_state=42,
        )
        self.model = self.MultiOutput(base_gp)
        self.model.fit(X, Y_scaled)

        self.is_fitted = True
        logger.info(f"GP surrogate fitted on {len(params_list)} samples")

    def predict(
        self, params: Any, return_std: bool = True
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Predict outputs for given parameters.

        Returns:
            predictions: Array of predicted values
            std: Standard deviations (if return_std=True)
        """
        if not self.is_fitted:
            # Return defaults
            return np.array([1.3, 14.0]), np.array([0.5, 5.0]) if return_std else None

        X = self.feature_extractor.extract(params).reshape(1, -1)

        # Get predictions from each estimator
        preds = []
        stds = []
        for estimator in self.model.estimators_:
            if return_std:
                pred, std = estimator.predict(X, return_std=True)
                preds.append(pred[0])
                stds.append(std[0])
            else:
                pred = estimator.predict(X)
                preds.append(pred[0])

        pred_scaled = np.array(preds)
        pred = self.scaler_y.inverse_transform(pred_scaled.reshape(1, -1))[0]

        if return_std:
            # Scale std back (approximate)
            std = np.array(stds) * self.scaler_y.scale_
            return pred, std
        return pred, None

    def get_acquisition_value(
        self, params: Any, best_f: float, xi: float = 0.01
    ) -> float:
        """
        Calculate Expected Improvement acquisition function.

        Args:
            params: Parameters to evaluate
            best_f: Best objective value found so far
            xi: Exploration-exploitation trade-off
        """
        from scipy.stats import norm

        pred, std = self.predict(params)
        if std is None or std[0] < 1e-10:
            return 0.0

        # EI for drag (first output)
        z = (best_f - pred[0] - xi) / std[0]
        ei = (best_f - pred[0] - xi) * norm.cdf(z) + std[0] * norm.pdf(z)

        return float(max(ei, 0))


class NeuralSurrogate:
    """
    Neural Network surrogate model for larger datasets.

    Best for:
    - Larger datasets (>100 samples)
    - Complex nonlinear relationships
    - Fast inference after training
    """

    def __init__(self, hidden_layers: List[int] = None):
        self.feature_extractor = FeatureExtractor()
        self.model = None
        self.scaler_y = None
        self.is_fitted = False
        self.hidden_layers = hidden_layers or [64, 32, 16]

        try:
            from sklearn.neural_network import MLPRegressor
            from sklearn.preprocessing import StandardScaler

            self.MLP = MLPRegressor
            self.StandardScaler = StandardScaler
            self.sklearn_available = True
        except ImportError:
            self.sklearn_available = False
            logger.warning("sklearn not available for Neural surrogate")

    def fit(
        self,
        params_list: List[Any],
        results: np.ndarray,
        epochs: int = 500,
        early_stopping: bool = True,
    ):
        """Fit neural network on training data."""
        if not self.sklearn_available:
            return

        X = self.feature_extractor.extract_batch(params_list)
        Y = np.array(results)

        self.scaler_y = self.StandardScaler()
        Y_scaled = self.scaler_y.fit_transform(Y)

        self.model = self.MLP(
            hidden_layer_sizes=tuple(self.hidden_layers),
            activation='relu',
            solver='adam',
            max_iter=epochs,
            early_stopping=early_stopping,
            validation_fraction=0.1,
            n_iter_no_change=20,
            random_state=42,
        )
        self.model.fit(X, Y_scaled)

        self.is_fitted = True
        logger.info(f"Neural surrogate fitted on {len(params_list)} samples")

    def predict(self, params: Any) -> np.ndarray:
        """Predict outputs for given parameters."""
        if not self.is_fitted:
            return np.array([1.3, 14.0])

        X = self.feature_extractor.extract(params).reshape(1, -1)
        pred_scaled = self.model.predict(X)
        pred = self.scaler_y.inverse_transform(pred_scaled)[0]

        return pred


class EnsembleSurrogate:
    """
    Ensemble surrogate combining GP and Neural Network.

    Uses GP for uncertainty estimation and NN for mean prediction,
    weighted by number of training samples.
    """

    def __init__(self):
        self.gp = GPSurrogate()
        self.nn = NeuralSurrogate()
        self.n_samples = 0
        self.gp_weight = 1.0

    def fit(self, params_list: List[Any], results: np.ndarray):
        """Fit both models on training data."""
        self.n_samples = len(params_list)

        # Fit GP (always)
        if self.n_samples >= 5:
            self.gp.fit(params_list, results)

        # Fit NN for larger datasets
        if self.n_samples >= 30:
            self.nn.fit(params_list, results)

        # Adjust weights based on sample size
        # GP dominates early, NN takes over with more data
        self.gp_weight = max(0.3, 1.0 - (self.n_samples - 30) / 100)

    def predict(
        self, params: Any, return_std: bool = True
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Ensemble prediction with uncertainty.

        Returns weighted combination of GP and NN predictions.
        Uncertainty comes from GP.
        """
        gp_pred, gp_std = self.gp.predict(params, return_std=True)

        if self.nn.is_fitted and self.gp_weight < 1.0:
            nn_pred = self.nn.predict(params)
            # Weighted average
            pred = self.gp_weight * gp_pred + (1 - self.gp_weight) * nn_pred
        else:
            pred = gp_pred

        return pred, gp_std

    def get_confidence(self, params: Any) -> float:
        """Get prediction confidence (0-1)."""
        _, std = self.predict(params)
        if std is None:
            return 0.0

        # Normalize std to confidence
        # Lower std = higher confidence
        avg_std = np.mean(std)
        confidence = np.exp(-avg_std / 2)  # Exponential decay

        return float(np.clip(confidence, 0, 1))


class CFDSurrogateDatabase:
    """
    Database for storing and loading CFD results for surrogate training.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.data_file = self.db_path / "cfd_data.json"
        self.data: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        """Load existing data from disk."""
        if self.data_file.exists():
            with open(self.data_file, 'r') as f:
                self.data = json.load(f)
            logger.info(f"Loaded {len(self.data)} CFD samples from database")

    def save(self):
        """Save data to disk."""
        with open(self.data_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def add_result(
        self,
        params: Dict[str, Any],
        drag: float,
        side_force: float,
        lift: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Add a CFD result to database."""
        entry = {
            'params': params,
            'drag': drag,
            'side_force': side_force,
            'lift': lift,
            'metadata': metadata or {},
        }
        self.data.append(entry)
        self.save()

    def get_training_data(
        self,
    ) -> Tuple[List[Dict[str, Any]], np.ndarray]:
        """
        Get all data formatted for surrogate training.

        Returns:
            params_list: List of parameter dictionaries
            results: Array of [drag, side_force] for each sample
        """
        params_list = [d['params'] for d in self.data]
        results = np.array([[d['drag'], d['side_force']] for d in self.data])

        return params_list, results

    def find_similar(
        self, params: Dict[str, Any], threshold: float = 0.1
    ) -> Optional[Dict[str, Any]]:
        """
        Find similar parameters in database.

        Returns cached result if parameters are within threshold distance.
        """
        # TODO: Implement parameter similarity search
        return None


def create_physics_informed_features(params: Any) -> np.ndarray:
    """
    Create physics-informed features for surrogate model.

    These features encode aerodynamic knowledge:
    - Aspect ratios
    - Wetted area estimates
    - Flow regime indicators
    """
    features = []

    # Rim aspect ratio (depth/width) - affects boundary layer
    rim_ar = params.rim_depth / max(params.rim_width_outer, 0.001)
    features.append(rim_ar)

    # Tire bulge ratio - affects separation
    tire_bulge = params.tire_width / max(params.rim_width_outer, 0.001)
    features.append(tire_bulge)

    # Spoke density (spokes per circumference length)
    circumference = np.pi * params.outer_diameter
    spoke_density = params.spoke_count / circumference
    features.append(spoke_density)

    # Estimated wetted area ratio
    rim_area = np.pi * params.outer_diameter * params.rim_depth
    spoke_area = params.spoke_count * params.spoke_diameter * (
        params.outer_diameter / 2 - params.hub_diameter / 2
    )
    total_area = rim_area + spoke_area
    features.append(total_area)

    # Profile shape indicator
    profile_score = {
        'toroidal': 0.3,
        'v_shape': 0.5,
        'box': 0.8,
        'aero': 0.2,
    }.get(params.rim_profile, 0.5)
    features.append(profile_score)

    # Bladed spoke effectiveness
    if params.spoke_profile == 'bladed':
        blade_ar = params.spoke_blade_width / max(params.spoke_diameter, 0.001)
        features.append(blade_ar)
    else:
        features.append(1.0)

    return np.array(features, dtype=np.float32)
