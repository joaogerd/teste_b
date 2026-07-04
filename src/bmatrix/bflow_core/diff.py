"""NMC perturbation calculation using configured product names."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

import netCDF4
import numpy as np

from .model import BflowPair, compact_time, product_name
from .netcdf_utils import copy_attrs


def diff_file(f48: Path, f24: Path, output: Path, valid_time: str) -> None:
    """Write a NetCDF file containing ``f48 - f24`` for common numeric fields."""
    output.unlink(missing_ok=True)
    with netCDF4.Dataset(f48) as ds48, netCDF4.Dataset(f24) as ds24, netCDF4.Dataset(output, "w") as dst:
        for name, dimension in ds48.dimensions.items():
            dst.createDimension(name, None if dimension.isunlimited() else len(dimension))
        copy_attrs(ds48, dst)
        dst.setncattr("nmc_difference", "older_minus_newer")
        dst.setncattr("valid_time", valid_time)
        dst.setncattr("source_older", str(f48))
        dst.setncattr("source_newer", str(f24))
        for name in (name for name in ds48.variables if name in ds24.variables):
            older, newer = ds48.variables[name], ds24.variables[name]
            if older.dimensions != newer.dimensions or not np.issubdtype(older.dtype, np.number):
                continue
            kwargs: dict[str, object] = {}
            fill_value = getattr(older, "_FillValue", None)
            if fill_value is not None:
                kwargs["fill_value"] = fill_value
            result = dst.createVariable(name, older.dtype, older.dimensions, **kwargs)
            copy_attrs(older, result)
            result.setncattr("nmc_operation", "older_minus_newer")
            result[:] = older[:] - newer[:]


def diff_pairs(config: Mapping[str, object], workspace: str | Path, pairs: list[BflowPair]) -> None:
    """Create the configured PTB product for each valid time."""
    root = Path(workspace)
    older = product_name(config, "older_full")
    newer = product_name(config, "newer_full")
    perturbation = product_name(config, "perturbation")
    for pair in pairs:
        directory = root / "output" / compact_time(pair.valid_time)
        diff_file(directory / older, directory / newer, directory / perturbation, pair.valid_time)
