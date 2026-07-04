"""Sparse ESMF weight access used by the BFLOW wind transformation.

Weight generation is delegated to :mod:`bmatrix.esmf_weights`, the standalone
ESMPy implementation supplied with this project.  This module deliberately
contains only sparse-file consumption and the small B-matrix configuration
adapter; it no longer has a second, divergent ESMF mesh implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ..errors import ArtifactError, ConfigurationError
from ..esmf_weights.config import from_bmatrix_config
from ..esmf_weights.generator import generate_weights
from ..esmf_weights.output import validate_weight_file


@dataclass(frozen=True, slots=True)
class EsmfSparseWeights:
    """Sparse weight matrix stored in ESMF's ``row``, ``col`` and ``S`` form."""

    path: Path
    row: np.ndarray
    col: np.ndarray
    weights: np.ndarray
    src_size: int
    dst_size: int
    src_grid_dims: tuple[int, ...]
    dst_grid_dims: tuple[int, ...]


def _dims(dataset: Any, name: str) -> tuple[int, ...]:
    """Read positive grid dimensions from an optional ESMF metadata variable."""
    if name not in dataset.variables:
        return ()
    return tuple(int(value) for value in np.asarray(dataset[name][:]).ravel() if int(value) > 0)


def _check(path: Path) -> None:
    """Validate a sparse ESMF file before it enters scientific processing."""
    if not path.is_file():
        raise ArtifactError(f"Pesos ESMF ausentes: {path}")
    try:
        validate_weight_file(path)
    except Exception as exc:
        raise ArtifactError(f"Pesos ESMF inválidos: {path}: {exc}") from exc


def load_esmf_sparse_weights(path: str | Path) -> EsmfSparseWeights:
    """Load one ESMF sparse matrix with zero-based indices for NumPy."""
    source = Path(path)
    _check(source)
    from netCDF4 import Dataset
    with Dataset(source) as dataset:
        row = np.asarray(dataset["row"][:], dtype=np.int64).ravel() - 1
        col = np.asarray(dataset["col"][:], dtype=np.int64).ravel() - 1
        coefficients = np.asarray(dataset["S"][:], dtype=np.float64).ravel()
        src_dims = _dims(dataset, "src_grid_dims")
        dst_dims = _dims(dataset, "dst_grid_dims")
    if row.size == 0 or col.size == 0 or row.min() < 0 or col.min() < 0:
        raise ArtifactError(f"Índices ESMF inválidos: {source}")
    return EsmfSparseWeights(
        path=source,
        row=row,
        col=col,
        weights=coefficients,
        src_size=int(np.prod(src_dims)) if src_dims else int(col.max()) + 1,
        dst_size=int(np.prod(dst_dims)) if dst_dims else int(row.max()) + 1,
        src_grid_dims=src_dims,
        dst_grid_dims=dst_dims,
    )


def apply_esmf_weights(values: np.ndarray, weights: EsmfSparseWeights) -> np.ndarray:
    """Apply sparse ESMF weights to arrays shaped ``(levels, source_points)``."""
    array = np.asarray(values)
    if array.ndim != 2 or array.shape[1] != weights.src_size:
        raise ArtifactError(
            f"Shape incompatível para {weights.path}: recebido={array.shape}; "
            f"esperado=(*, {weights.src_size})."
        )
    output = np.zeros((array.shape[0], weights.dst_size), dtype=np.float64)
    for level in range(array.shape[0]):
        np.add.at(output[level], weights.row, array[level, weights.col] * weights.weights)
    return output


def latlon_shape_from_weights(weights: EsmfSparseWeights) -> tuple[int, int]:
    """Return regular-grid shape as ``(nlat, nlon)`` from ESMF metadata."""
    dimensions = weights.dst_grid_dims or weights.src_grid_dims
    if len(dimensions) < 2:
        raise ArtifactError(f"Dimensões lat/lon ausentes em {weights.path}")
    return int(dimensions[1]), int(dimensions[0])


def _regridding(config: Mapping[str, object]) -> Mapping[str, object]:
    bflow = config.get("bflow")
    if not isinstance(bflow, Mapping) or not isinstance(bflow.get("regridding"), Mapping):
        raise ConfigurationError("bflow.regridding deve ser um bloco YAML.")
    return bflow["regridding"]


def _weight_directory(config: Mapping[str, object], workspace: str | Path) -> Path:
    regridding = _regridding(config)
    mesh = config.get("mesh")
    if not isinstance(mesh, Mapping):
        raise ConfigurationError("mesh deve ser um bloco YAML.")
    directory = str(regridding.get("weights_directory", "ESMF_weights"))
    directory = directory.format(mesh_name=mesh["name"])
    output = Path(directory).expanduser()
    return output if output.is_absolute() else Path(workspace) / output


def weight_paths(config: Mapping[str, object], workspace: str | Path) -> tuple[Path, Path]:
    """Return ``(MPAS→latlon, latlon→MPAS)`` paths used by BFLOW."""
    settings = from_bmatrix_config(config, output_dir=_weight_directory(config, workspace))
    latlon_to_mpas, mpas_to_latlon = settings.output_paths()
    return mpas_to_latlon, latlon_to_mpas


def ensure_esmf_weights(config: Mapping[str, object], workspace: str | Path) -> tuple[Path, Path]:
    """Require and validate both deterministic ESMF products."""
    paths = weight_paths(config, workspace)
    for path in paths:
        _check(path)
    return paths


def generate_esmf_weights(
    config: Mapping[str, object],
    workspace: str | Path,
    *,
    force: bool = False,
) -> tuple[Path, Path]:
    """Generate MPAS/lat-lon weights through the integrated ESMPy code.

    The generator runs in serial and writes a provenance manifest into the
    workspace-local ``ESMF_weights`` directory.  If only one file exists, both
    are regenerated together to preserve a coherent pair.
    """
    output_dir = _weight_directory(config, workspace)
    settings = from_bmatrix_config(config, output_dir=output_dir, force=force)
    forward, reverse = settings.output_paths()
    existing = [path for path in (forward, reverse) if path.exists()]
    if len(existing) == 2 and not force:
        return ensure_esmf_weights(config, workspace)
    if existing and not force:
        settings = from_bmatrix_config(config, output_dir=output_dir, force=True)
    generate_weights(settings, progress=print)
    return ensure_esmf_weights(config, workspace)
