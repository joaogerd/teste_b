"""NMC campaign manifest validation for the B-matrix consumer workflow."""

from .checks import validate_manifest
from .manifest import read_manifest

__all__ = ["read_manifest", "validate_manifest"]
