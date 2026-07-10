"""Static-file preparation for SO without hard-coded background contracts."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

import numpy as np

from ..bflow_core.netcdf_utils import CDF5_FORMAT
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


def validate_analysis_output(path: Path, required_variables: Iterable[str]) -> bool:
    """Require the SO output file to contain MPAS-native analysis fields."""
    import netCDF4

    required = list(dict.fromkeys(required_variables))
    if not required:
        raise RuntimeError("Lista de variáveis de análise vazia para validar saída SO.")
    try:
        with netCDF4.Dataset(path) as dataset:
            present = [name for name in required if name in dataset.variables]
            missing = [name for name in required if name not in dataset.variables]
            data_model = dataset.data_model
    except OSError as exc:
        raise RuntimeError(f"Saída de análise MPAS {path} não pôde ser lida como NetCDF: {exc}") from exc
    if missing:
        raise RuntimeError(
            f"Saída de análise MPAS {path} não contém variáveis nativas esperadas: "
            f"{', '.join(missing)}. Presentes: {', '.join(present) or 'nenhuma'}"
        )
    if data_model != CDF5_FORMAT:
        raise RuntimeError(f"Saída de análise MPAS {path} não está em CDF5: {data_model}")
    return True


def _copy_variable(dataset: object, source_name: str, target_name: str, long_name: str, units: str) -> None:
    source = dataset.variables[source_name]
    variable = dataset.createVariable(target_name, source.dtype, source.dimensions)
    variable[:] = source[:]
    variable.setncattr("long_name", long_name)
    variable.setncattr("units", units)


def _ensure_moist_air_specific_humidity(dataset: object) -> None:
    target = "water_vapor_mixing_ratio_wrt_moist_air"
    if target in dataset.variables:
        return
    if "spechum" in dataset.variables:
        _copy_variable(dataset, "spechum", target, "water vapor mixing ratio wrt moist air", "kg kg-1")
        return
    if "qv" not in dataset.variables:
        raise RuntimeError(
            "Background SO sem umidade para criar water_vapor_mixing_ratio_wrt_moist_air: "
            "variáveis spechum e qv ausentes."
        )
    qv = dataset.variables["qv"]
    values = np.asarray(qv[:]) / (1.0 + np.asarray(qv[:]))
    variable = dataset.createVariable(target, qv.dtype, qv.dimensions)
    variable[:] = values.astype(qv.dtype, copy=False)
    variable.setncattr("long_name", "water vapor mixing ratio wrt moist air")
    variable.setncattr("units", "kg kg-1")


def _available(dataset: object, names: tuple[str, ...]) -> bool:
    return all(name in dataset.variables for name in names)


def _add_derived_background_variables(dataset: object) -> None:
    if "pressure" not in dataset.variables and _available(dataset, ("pressure_base", "pressure_p")):
        pressure_p = dataset.variables["pressure_p"]
        pressure = dataset.variables["pressure_base"][:] + pressure_p[:]
        variable = dataset.createVariable("pressure", pressure_p.dtype, pressure_p.dimensions)
        variable[:] = pressure.astype(pressure_p.dtype, copy=False)
        variable.setncattr("long_name", "pressure")
        variable.setncattr("units", "Pa")
    if "air_pressure" not in dataset.variables and "pressure" in dataset.variables:
        _copy_variable(dataset, "pressure", "air_pressure", "air pressure", "Pa")
    if "air_pressure_at_surface" not in dataset.variables and "surface_pressure" in dataset.variables:
        _copy_variable(dataset, "surface_pressure", "air_pressure_at_surface", "air pressure at surface", "Pa")
    if "spechum" not in dataset.variables and "qv" in dataset.variables:
        qv = dataset.variables["qv"]
        variable = dataset.createVariable("spechum", qv.dtype, qv.dimensions)
        variable[:] = (qv[:] / (1.0 + qv[:])).astype(qv.dtype, copy=False)
        variable.setncattr("long_name", "specific humidity")
        variable.setncattr("units", "kg kg-1")
    if "air_temperature" not in dataset.variables and _available(dataset, ("theta", "pressure")):
        theta = dataset.variables["theta"]
        values = theta[:] * (dataset.variables["pressure"][:] / 100000.0) ** (2.0 / 7.0)
        variable = dataset.createVariable("air_temperature", theta.dtype, theta.dimensions)
        variable[:] = values.astype(theta.dtype, copy=False)
        variable.setncattr("long_name", "air temperature")
        variable.setncattr("units", "K")
    if "temperature" not in dataset.variables and "air_temperature" in dataset.variables:
        _copy_variable(dataset, "air_temperature", "temperature", "temperature", "K")
    if "eastward_wind" not in dataset.variables and "uReconstructZonal" in dataset.variables:
        _copy_variable(dataset, "uReconstructZonal", "eastward_wind", "eastward wind", "m s-1")
    if "northward_wind" not in dataset.variables and "uReconstructMeridional" in dataset.variables:
        _copy_variable(dataset, "uReconstructMeridional", "northward_wind", "northward wind", "m s-1")


def create_jedi_background(source: Path, output: Path, required_variables: Iterable[str], context: str) -> None:
    """Create a JEDI background file and derive configured aliases when possible."""
    import netCDF4

    source = require_file(source.resolve(), f"background MPAS {context}")
    output.unlink(missing_ok=True)
    shutil.copy2(source, output)
    with netCDF4.Dataset(output, "a") as dataset:
        _add_derived_background_variables(dataset)
        _ensure_moist_air_specific_humidity(dataset)
    validate_so_background(output, required_variables)


def create_so_background(source: Path, output: Path, required_variables: Iterable[str]) -> None:
    """Create a background file and add common derived MPAS fields when needed."""
    import netCDF4
    source = require_file(source.resolve(), "template MPAS completo")
    output.unlink(missing_ok=True)
    shutil.copy2(source, output)
    with netCDF4.Dataset(output, "a") as dataset:
        native = ("pressure_base", "pressure_p", "theta", "surface_pressure", "uReconstructZonal", "uReconstructMeridional")
        missing = [name for name in native if name not in dataset.variables]
        if missing:
            raise RuntimeError("Template MPAS sem variáveis nativas SO: " + ", ".join(missing))
        if "spechum" not in dataset.variables and "qv" not in dataset.variables:
            raise RuntimeError("Template MPAS sem variáveis nativas SO: spechum ou qv")
        pressure_p = dataset.variables["pressure_p"]
        pressure = dataset.variables["pressure_base"][:] + pressure_p[:]
        theta = dataset.variables["theta"]
        derived = {
            "pressure": (pressure_p, pressure, "pressure", "Pa"),
            "air_pressure": (pressure_p, pressure, "air pressure", "Pa"),
            "air_pressure_at_surface": (dataset.variables["surface_pressure"], dataset.variables["surface_pressure"][:], "air pressure at surface", "Pa"),
            "temperature": (theta, theta[:] * (pressure / 100000.0) ** (2.0 / 7.0), "temperature", "K"),
            "air_temperature": (theta, theta[:] * (pressure / 100000.0) ** (2.0 / 7.0), "air temperature", "K"),
            "eastward_wind": (dataset.variables["uReconstructZonal"], dataset.variables["uReconstructZonal"][:], "eastward wind", "m s-1"),
            "northward_wind": (dataset.variables["uReconstructMeridional"], dataset.variables["uReconstructMeridional"][:], "northward wind", "m s-1"),
        }
        if "spechum" not in dataset.variables:
            qv = dataset.variables["qv"]
            derived["spechum"] = (qv, qv[:] / (1.0 + qv[:]), "specific humidity", "kg kg-1")
        for name, (template, values, long_name, units) in derived.items():
            if name not in dataset.variables:
                variable = dataset.createVariable(name, template.dtype, template.dimensions)
                variable[:] = values.astype(template.dtype, copy=False)
                variable.setncattr("long_name", long_name)
                variable.setncattr("units", units)
        _ensure_moist_air_specific_humidity(dataset)
    validate_so_background(output, required_variables)
