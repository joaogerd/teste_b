"""Single-observation workspace paths and executable resolution."""
from __future__ import annotations

from pathlib import Path

from ..shell import require_file
from ..vbal_core.model import covariance_root

SO_VARIANTS = ("default", "t-only", "u-only")


def so_workspace(config, nicas_workspace_path: str | Path) -> Path:
    """Return the deterministic SO workspace for a NICAS workspace."""
    return covariance_root(config) / "so" / Path(nicas_workspace_path).name


def variational_exe(config) -> Path:
    """Resolve the installed MPAS-JEDI variational executable."""
    return require_file(Path(config["install"]["root"]) / "bin" / "mpasjedi_variational.x", "mpasjedi_variational.x")


def so_artifacts(variant: str) -> dict[str, str]:
    """Return file names owned by one supported SO variant."""
    if variant not in SO_VARIANTS:
        raise ValueError(f"Variante SO inválida: {variant}; use {', '.join(SO_VARIANTS)}.")
    suffix = "" if variant == "default" else f"_{variant.replace('-', '_')}"
    return {
        "yaml": f"run_SO{suffix}.yaml",
        "pbs": f"qsub_so{suffix}.bash",
        "runlog": f"run_SO{suffix}.runlog",
        "stdout": f"stdout{suffix}.log",
        "stderr": f"stderr{suffix}.log",
    }
