from __future__ import annotations

from pathlib import Path

from .model import vbal_workspace


def workspace(config, bflow_workspace: str | Path) -> Path:
    """Return the default VBAL workspace for a BFLOW workspace."""
    return vbal_workspace(config, bflow_workspace)
