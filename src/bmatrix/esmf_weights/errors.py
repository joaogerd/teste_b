"""Domain-specific exceptions for MPAS ESMF weight generation."""
from __future__ import annotations

from bmatrix.errors import BMatrixError, ConfigurationError as BMatrixConfigurationError


class ConfigurationError(BMatrixConfigurationError):
    """Raised when the ESMF weights configuration is invalid."""


class DependencyError(BMatrixError, RuntimeError):
    """Raised when an optional runtime dependency required for generation is unavailable."""


class WeightValidationError(BMatrixError, ValueError):
    """Raised when a generated ESMF sparse weight file is invalid."""
