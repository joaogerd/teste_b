"""Project-wide error types.

The command-line layer converts these errors into concise exit messages. Library
modules should raise these exceptions rather than printing or calling
``SystemExit`` directly.
"""
from __future__ import annotations


class BMatrixError(Exception):
    """Base exception for operational errors in the B-matrix workflow."""


class ConfigurationError(BMatrixError, ValueError):
    """Raised when a platform or scientific configuration is invalid."""


class WorkflowError(BMatrixError, RuntimeError):
    """Raised when a workflow stage cannot be planned or completed."""


class ArtifactError(WorkflowError):
    """Raised when expected input or output artifacts are absent or invalid."""
