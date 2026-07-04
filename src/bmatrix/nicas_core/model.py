"""NICAS workspace paths."""
from __future__ import annotations

from pathlib import Path

from ..vbal_core.model import covariance_root


def nicas_workspace(config, hdiag_workspace_path: str | Path) -> Path:
    """Return the deterministic NICAS workspace for an HDIAG workspace."""
    return covariance_root(config) / "nicas" / Path(hdiag_workspace_path).name
