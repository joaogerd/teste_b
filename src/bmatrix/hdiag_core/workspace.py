from __future__ import annotations

from pathlib import Path

from .model import hdiag_workspace


def workspace(config, vbal_workspace: str | Path) -> Path:
    """Return the default HDIAG workspace for a VBAL workspace."""
    return hdiag_workspace(config, vbal_workspace)
