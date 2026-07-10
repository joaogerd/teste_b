"""Validation of complete-B DIRAC outputs."""
from __future__ import annotations

import re
from pathlib import Path

DIRAC_PRODUCT = "mpas.dirac.nc"


def _is_netcdf(path: Path) -> bool:
    import netCDF4

    try:
        with netCDF4.Dataset(path):
            return True
    except OSError:
        return False


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
    product = root / DIRAC_PRODUCT
    if not product.is_file():
        errors.append(f"produto DIRAC ausente: {DIRAC_PRODUCT}")
    elif not _is_netcdf(product):
        errors.append(f"produto DIRAC não é NetCDF válido: {DIRAC_PRODUCT}")
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
