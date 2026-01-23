"""
WheelFlow Geometry Optimization Module

AI-driven optimization system for bicycle wheel aerodynamics.
Uses parametric geometry generation with various optimization algorithms.

Supported optimization methods:
- Bayesian Optimization (Optuna) - efficient for expensive CFD simulations
- NSGA-II - multi-objective Pareto optimization
- Random Search - baseline comparison

Surrogate modeling:
- Gaussian Process (GP) for uncertainty quantification
- Neural Network for large datasets
- Ensemble methods for best of both

Supported geometry backends:
- Direct STL generation (built-in)
- OpenSCAD (parametric CSG)
- CadQuery (Python CAD) - planned
"""

from .parametric_wheel import (
    ParametricWheel,
    WheelParameters,
    create_optimization_bounds,
    create_categorical_options,
)
from .optimizer import (
    WheelOptimizer,
    OptimizationConfig,
    OptimizationResult,
    SurrogateModel,
    create_cfd_runner,
)
from .surrogate import (
    GPSurrogate,
    NeuralSurrogate,
    EnsembleSurrogate,
    FeatureExtractor,
    CFDSurrogateDatabase,
)

__all__ = [
    # Geometry
    'ParametricWheel',
    'WheelParameters',
    'create_optimization_bounds',
    'create_categorical_options',
    # Optimization
    'WheelOptimizer',
    'OptimizationConfig',
    'OptimizationResult',
    'SurrogateModel',
    'create_cfd_runner',
    # Surrogate models
    'GPSurrogate',
    'NeuralSurrogate',
    'EnsembleSurrogate',
    'FeatureExtractor',
    'CFDSurrogateDatabase',
]
