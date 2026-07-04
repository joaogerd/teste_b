from __future__ import annotations

from pathlib import Path

from .model import so_workspace


def workspace(config, nicas_workspace: str | Path) -> Path:
    """Return the default SO workspace for a NICAS workspace."""
    return so_workspace(config, nicas_workspace)
