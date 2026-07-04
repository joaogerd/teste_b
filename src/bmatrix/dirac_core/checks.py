"""Validation of complete-B DIRAC outputs."""
from __future__ import annotations

import re
from pathlib import Path


def check(workspace: str | Path) -> bool:
    """Validate the toolbox success marker and ``mpas.dirac.nc`` output."""
    root = Path(workspace)
    runlog = root / "run_dirac.runlog"
    text = runlog.read_text(errors="replace") if runlog.is_file() else ""
    errors: list[str] = []
    if not runlog.is_file():
        errors.append("run_dirac.runlog ausente")
    if "Finishing oops::ErrorCovarianceToolbox<MPAS> with status = 0" not in text:
        errors.append("status final de sucesso ausente no run_dirac.runlog")
    if not (root / "mpas.dirac.nc").is_file():
        errors.append("produto DIRAC ausente: mpas.dirac.nc")
    combined = "\n".join(
        path.read_text(errors="replace")
        for path in (runlog, root / "stdout.log", root / "stderr.log")
        if path.is_file()
    )
    statuses = re.findall(r"with status\s*=\s*(-?\d+)", combined)
    if any(status != "0" for status in statuses):
        errors.append("status não nulo encontrado nos logs DIRAC")
    if errors:
        raise RuntimeError("DIRAC falhou ou ficou incompleto: " + "; ".join(errors))
    return True
