"""Static-file preparation for SO without hard-coded background contracts."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

from ..nicas_core.static import link_nicas_support
from ..shell import require_file


def link_so_support(hdiag_run: Path, run_dir: Path) -> Path:
    """Link geometry and physics support, returning the MPAS template field file."""
    link_nicas_support(hdiag_run, run_dir)
    (run_dir / "bg.nc").unlink(missing_ok=True)
    templates = sorted(hdiag_run.glob("templateFields.*.nc"))
    if len(templates) != 1:
        raise RuntimeError("Esperado exatamente um templateFields.*.nc no workspace HDIAG.")
    return templates[0]


def validate_so_background(path: Path, required_variables: Iterable[str]) -> bool:
    """Validate declared SO background variables in a prepared NetCDF file."""
    import netCDF4
    with netCDF4.Dataset(path) as dataset:
        missing = [name for name in required_variables if name not in dataset.variables]
    if missing:
        raise RuntimeError(f"Background SO incompleto em {path}: {', '.join(missing)}")
    return True


def create_so_background(source: Path, output: Path, required_variables: Iterable[str]) -> None:
    """Create a background file and add common derived MPAS fields when needed."""
    import netCDF4
    source = require_file(source.resolve(), "template MPAS completo")
    output.unlink(missing_ok=True)
    shutil.copy2(source, output)
    with netCDF4.Dataset(output, "a") as dataset:
        native = ("pressure_base", "pressure_p", "theta", "qv", "surface_pressure", "uReconstructZonal", "uReconstructMeridional")
        missing = [name for name in native if name not in dataset.variables]
        if missing:
            raise RuntimeError("Template MPAS sem variáveis nativas SO: " + ", ".join(missing))
        pressure_p = dataset.variables["pressure_p"]
        pressure = dataset.variables["pressure_base"][:] + pressure_p[:]
        theta = dataset.variables["theta"]
        qv = dataset.variables["qv"]
        derived = {
            "pressure": (pressure_p, pressure, "pressure", "Pa"),
            "air_pressure": (pressure_p, pressure, "air pressure", "Pa"),
            "air_pressure_at_surface": (dataset.variables["surface_pressure"], dataset.variables["surface_pressure"][:], "air pressure at surface", "Pa"),
            "temperature": (theta, theta[:] * (pressure / 100000.0) ** (2.0 / 7.0), "temperature", "K"),
            "air_temperature": (theta, theta[:] * (pressure / 100000.0) ** (2.0 / 7.0), "air temperature", "K"),
            "spechum": (qv, qv[:] / (1.0 + qv[:]), "specific humidity", "kg kg-1"),
            "eastward_wind": (dataset.variables["uReconstructZonal"], dataset.variables["uReconstructZonal"][:], "eastward wind", "m s-1"),
            "northward_wind": (dataset.variables["uReconstructMeridional"], dataset.variables["uReconstructMeridional"][:], "northward wind", "m s-1"),
        }
        for name, (template, values, long_name, units) in derived.items():
            if name not in dataset.variables:
                variable = dataset.createVariable(name, template.dtype, template.dimensions)
                variable[:] = values.astype(template.dtype, copy=False)
                variable.setncattr("long_name", long_name)
                variable.setncattr("units", units)
    validate_so_background(output, required_variables)
