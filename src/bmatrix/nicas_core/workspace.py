from __future__ import annotations

from pathlib import Path

from .model import nicas_workspace


def workspace(config, hdiag_workspace: str | Path) -> Path:
    """Return the default NICAS workspace for an HDIAG workspace."""
    return nicas_workspace(config, hdiag_workspace)
