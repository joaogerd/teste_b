"""Workspace conventions for full-B DIRAC diagnostics."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from ..vbal_core.model import covariance_root


def dirac_workspace(config: Mapping[str, object], nicas_workspace_path: str | Path) -> Path:
    """Return the deterministic DIRAC workspace for one NICAS calibration."""
    return covariance_root(config) / "dirac" / Path(nicas_workspace_path).name
