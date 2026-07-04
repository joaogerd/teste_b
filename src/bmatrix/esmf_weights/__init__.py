"""Reusable API for MPAS <-> latitude-longitude ESMF weight generation.

Examples
--------
>>> from pathlib import Path
>>> from bmatrix.esmf_weights import generate_weights, load_config
>>> config = load_config(Path("generate_esmf_weights.yaml"))
>>> result = generate_weights(config)
"""

from __future__ import annotations

from .config import WeightGenerationConfig, load_config
from .constants import PACKAGE_VERSION
from .errors import ConfigurationError, DependencyError, WeightValidationError
from .generator import GenerationResult, ProgressReporter, generate_weights
from .mpas import MpasMeshData, read_mpas_mesh
from .output import WeightValidation, validate_weight_file

__version__ = PACKAGE_VERSION

__all__ = [
    "ConfigurationError",
    "DependencyError",
    "GenerationResult",
    "MpasMeshData",
    "ProgressReporter",
    "WeightGenerationConfig",
    "WeightValidation",
    "WeightValidationError",
    "generate_weights",
    "load_config",
    "read_mpas_mesh",
    "validate_weight_file",
]
