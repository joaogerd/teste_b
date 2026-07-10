from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from ..shell import require_file
from ..vbal_core.model import covariance_root


UNBALANCE_EXE_DEFAULT = (
    "/p/projetos/monan_das/joao.gerd/projects/MONAN-JEDI/"
    "build-unbalance/bin/mpasjedi_unbalance_ensemble.x"
)


def unbalance_workspace(config: Mapping[str, object], vbal_workspace_path: str | Path) -> Path:
    """Resolve the deterministic UNBALANCE workspace for one VBAL run."""
    return covariance_root(config) / "unbalance" / Path(vbal_workspace_path).name


def unbalance_exe(config: Mapping[str, object]) -> Path:
    """Resolve the executable that applies K2^-1 to the centered perturbation ensemble."""
    section = config.get("unbalance", {})
    path = UNBALANCE_EXE_DEFAULT
    if isinstance(section, Mapping):
        path = str(section.get("executable", path))
    return require_file(path, "mpasjedi_unbalance_ensemble.x")


def vbal_date(vbal_root: str | Path) -> str:
    """Read the calibration date from a rendered VBAL YAML file."""
    text = require_file(Path(vbal_root) / "VBAL" / "run_vbal.yaml", "run_vbal.yaml").read_text()
    match = re.search(r"(?m)^\s*date:\s*([^ \n]+)", text)
    if not match:
        raise RuntimeError("Data principal não encontrada no run_vbal.yaml")
    return match.group(1).strip("'\"")

