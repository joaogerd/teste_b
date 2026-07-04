"""Output-file validation and provenance-manifest support."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from .config import WeightGenerationConfig
from .constants import GENERATOR_VERSION
from .errors import DependencyError, WeightValidationError
from .mpas import MpasMeshData
from .utils import sha256_file


@dataclass(frozen=True, slots=True)
class WeightValidation:
    """Quality checks calculated from one ESMF sparse weight file.

    Parameters
    ----------
    path
        Validated file path.
    entries
        Number of sparse nonzero weight entries.
    mapped_destinations
        Number of output rows containing at least one weight.
    minimum_weight
        Minimum sparse coefficient.
    maximum_weight
        Maximum sparse coefficient.
    max_abs_row_sum_error
        Maximum absolute deviation of a mapped destination row sum from one.
    nonfinite_weights
        Number of non-finite coefficients.
    """

    path: Path
    entries: int
    mapped_destinations: int
    minimum_weight: float
    maximum_weight: float
    max_abs_row_sum_error: float
    nonfinite_weights: int


def validate_weight_file(path: Path) -> WeightValidation:
    """Validate structure and row-sum normalization of an ESMF weight file.

    Parameters
    ----------
    path
        NetCDF sparse ESMF weight file containing ``row``, ``col``, and ``S``.

    Returns
    -------
    WeightValidation
        Sparse-file summary and normalization metrics.

    Raises
    ------
    DependencyError
        If ``netCDF4`` is not installed.
    WeightValidationError
        If the required sparse arrays are missing, inconsistent, empty, or
        contain non-finite coefficients.
    """
    Dataset = _netcdf_dataset()
    try:
        with Dataset(path, "r") as dataset:
            row = np.asarray(dataset.variables["row"][:], dtype=np.int64).reshape(-1)
            column = np.asarray(dataset.variables["col"][:], dtype=np.int64).reshape(-1)
            values = np.asarray(dataset.variables["S"][:], dtype=np.float64).reshape(-1)
    except KeyError as exc:
        raise WeightValidationError(
            f"Arquivo de pesos inválido '{path}': variáveis row, col e S são obrigatórias."
        ) from exc

    if not (row.size == column.size == values.size) or row.size == 0:
        raise WeightValidationError(
            f"Arquivo de pesos inválido '{path}': arrays vazios ou com tamanhos diferentes."
        )
    if np.any(row <= 0) or np.any(column <= 0):
        raise WeightValidationError(
            f"Arquivo de pesos inválido '{path}': índices row/col devem ser positivos."
        )
    nonfinite_weights = int(np.count_nonzero(~np.isfinite(values)))
    if nonfinite_weights:
        raise WeightValidationError(
            f"Arquivo de pesos inválido '{path}': contém {nonfinite_weights} peso(s) não finito(s)."
        )

    sums = np.bincount(row - 1, weights=values, minlength=int(row.max()))
    occupied = np.bincount(row - 1, minlength=int(row.max())) > 0
    errors = np.abs(sums[occupied] - 1.0)
    return WeightValidation(
        path=path,
        entries=int(values.size),
        mapped_destinations=int(np.count_nonzero(occupied)),
        minimum_weight=float(np.min(values)),
        maximum_weight=float(np.max(values)),
        max_abs_row_sum_error=float(np.max(errors)),
        nonfinite_weights=nonfinite_weights,
    )


def write_manifest(
    config: WeightGenerationConfig,
    outputs: Sequence[Path],
    *,
    nlat: int,
    nlon: int,
    mesh_data: MpasMeshData,
    validation: Sequence[WeightValidation],
) -> Path:
    """Write a JSON provenance manifest for a completed generation run.

    Parameters
    ----------
    config
        Validated generation configuration.
    outputs
        Generated ESMF weight files.
    nlat
        Number of latitude points in the regular grid.
    nlon
        Number of longitude points in the regular grid.
    mesh_data
        MPAS geometry and conversion provenance.
    validation
        Validation summaries for `outputs`.

    Returns
    -------
    pathlib.Path
        Manifest location, always ``weights_manifest.json`` in the configured
        output directory.

    Raises
    ------
    OSError
        If the manifest cannot be written.
    """
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator": GENERATOR_VERSION,
        "mpas": {
            "path": str(config.mpas_file),
            "sha256": sha256_file(config.mpas_file),
            "grid_id": config.mpas_grid_id,
            "lat_var": config.lat_var,
            "lon_var": config.lon_var,
            "connectivity_var": config.connectivity_var,
            **mesh_data.metadata,
        },
        "latlon": {
            "grid_id": config.latlon_grid_id,
            "shape": [nlat, nlon],
            "resolution_deg": config.resolution_deg,
            "ll_corner": list(config.ll_corner),
            "ur_corner": list(config.ur_corner),
        },
        "outputs": [
            {"path": str(item), "sha256": sha256_file(item)} for item in outputs
        ],
        "validation": [
            {**asdict(item), "path": str(item.path)} for item in validation
        ],
    }
    manifest_path = config.output_dir / "weights_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest_path


def _netcdf_dataset() -> Any:
    try:
        from netCDF4 import Dataset
    except ImportError as exc:
        raise DependencyError(
            "A dependência 'netCDF4' não está disponível. "
            "Instale-a com conda/pip antes de validar os pesos."
        ) from exc
    return Dataset
