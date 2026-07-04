"""MPAS mesh reading, validation, and coordinate-conversion utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from .config import WeightGenerationConfig
from .errors import DependencyError


@dataclass(frozen=True, slots=True)
class MpasMeshData:
    """MPAS dual-mesh data required by ESMF.

    Parameters
    ----------
    lat_deg
        One-dimensional MPAS cell latitudes in degrees.
    lon_deg
        One-dimensional MPAS cell longitudes in degrees.
    connectivity
        Counter-clockwise triangular dual-mesh connectivity with local
        zero-based cell indices and shape ``(n_vertices, 3)``.
    metadata
        Provenance metadata for the source coordinates and conversion mode.
    """

    lat_deg: np.ndarray
    lon_deg: np.ndarray
    connectivity: np.ndarray
    metadata: dict[str, Any]

    @property
    def n_cells(self) -> int:
        """Return the number of MPAS cells represented by the mesh."""
        return int(self.lat_deg.size)

    @property
    def n_triangles(self) -> int:
        """Return the number of dual-mesh triangular elements."""
        return int(self.connectivity.shape[0])


def read_mpas_mesh(config: WeightGenerationConfig) -> MpasMeshData:
    """Read and validate the MPAS mesh required for ESMF interpolation.

    Parameters
    ----------
    config
        Validated run configuration.

    Returns
    -------
    MpasMeshData
        Coordinates in degrees plus counter-clockwise local triangular
        connectivity.

    Raises
    ------
    FileNotFoundError
        If the configured MPAS file does not exist.
    DependencyError
        If the ``netCDF4`` package is not available.
    ValueError
        If required variables are missing or mesh geometry is invalid.

    Notes
    -----
    The function requires a closed global MPAS mesh. It rejects zero or
    negative connectivity indices because those represent invalid/boundary
    entries for this workflow.
    """
    if not config.mpas_file.is_file():
        raise FileNotFoundError(f"Arquivo MPAS não encontrado: {config.mpas_file}")

    Dataset = _netcdf_dataset()
    with Dataset(config.mpas_file, "r") as dataset:
        required = [config.lat_var, config.lon_var, config.connectivity_var]
        missing = [name for name in required if name not in dataset.variables]
        if missing:
            raise ValueError(f"Variáveis MPAS ausentes: {', '.join(missing)}")

        lat_var = dataset.variables[config.lat_var]
        lon_var = dataset.variables[config.lon_var]
        lat_raw = np.asarray(lat_var[:])
        lon_raw = np.asarray(lon_var[:])
        connectivity_raw = np.asarray(dataset.variables[config.connectivity_var][:])
        lat_units = detect_coordinate_units(lat_var, config.coordinate_units)
        lon_units = detect_coordinate_units(lon_var, config.coordinate_units)

    if lat_units != lon_units:
        raise ValueError("latCell e lonCell têm unidades incompatíveis.")
    if lat_raw.size != lon_raw.size:
        raise ValueError("latCell e lonCell têm tamanhos incompatíveis.")

    connectivity_raw = _normalize_connectivity_shape(connectivity_raw)
    if lat_units == "radians":
        lat_deg = radians_to_degrees(
            lat_raw, config.coordinate_conversion, lat_raw.dtype
        )
        lon_deg = radians_to_degrees(
            lon_raw, config.coordinate_conversion, lon_raw.dtype
        )
    else:
        lat_deg = np.asarray(lat_raw, dtype=np.float64)
        lon_deg = np.asarray(lon_raw, dtype=np.float64)

    connectivity = _validate_connectivity(connectivity_raw, lat_deg.size)
    connectivity = orient_counterclockwise(connectivity, lon_deg, lat_deg)

    metadata = {
        "coordinate_units": lat_units,
        "coordinate_conversion": config.coordinate_conversion,
        "input_dtype": str(lat_raw.dtype),
        "ncl_float32_r2d": _legacy_r2d_value_if_used(
            lat_units, config.coordinate_conversion, lat_raw.dtype
        ),
    }
    return MpasMeshData(
        lat_deg=lat_deg.reshape(-1),
        lon_deg=lon_deg.reshape(-1),
        connectivity=connectivity,
        metadata=metadata,
    )


def detect_coordinate_units(variable: Any, configured: str) -> str:
    """Determine MPAS coordinate units from configuration, metadata, or values.

    Parameters
    ----------
    variable
        NetCDF variable containing angular coordinates.
    configured
        Requested policy: ``"auto"``, ``"radians"``, or ``"degrees"``.

    Returns
    -------
    str
        Either ``"radians"`` or ``"degrees"``.

    Notes
    -----
    With ``"auto"``, CF-like metadata is preferred. If it is unavailable, the
    absolute value range is used as a last-resort heuristic.
    """
    if configured != "auto":
        return configured
    units = str(getattr(variable, "units", "")).lower()
    if "rad" in units:
        return "radians"
    if "degree" in units or "deg" in units:
        return "degrees"
    values = np.asarray(variable[:])
    maximum = float(np.nanmax(np.abs(values)))
    return "radians" if maximum <= (2.0 * math.pi + 0.1) else "degrees"


def radians_to_degrees(
    values: np.ndarray,
    mode: str,
    source_dtype: np.dtype[Any],
) -> np.ndarray:
    """Convert radians to degrees with an optional NCL-compatible float32 mode.

    Parameters
    ----------
    values
        Coordinate values in radians.
    mode
        ``"ncl_legacy"`` to reproduce the legacy NCL float32 arithmetic when
        the source type is float32, or ``"double"`` for float64 conversion.
    source_dtype
        Original NetCDF coordinate dtype.

    Returns
    -------
    numpy.ndarray
        Values in degrees with float64 storage.

    Notes
    -----
    NCL evaluated ``180.0 / (atan(1) * 4.0)`` in float32 for float input.
    Reproducing that detail preserves the legacy bilinear coefficients.
    """
    raw = np.asarray(values)
    if mode == "double" or source_dtype != np.dtype(np.float32):
        return np.rad2deg(np.asarray(raw, dtype=np.float64))

    one = np.float32(1.0)
    r2d = np.float32(np.float32(180.0) / (np.arctan(one) * np.float32(4.0)))
    converted = np.asarray(raw, dtype=np.float32) * r2d
    return np.asarray(converted, dtype=np.float64)


def orient_counterclockwise(
    connectivity: np.ndarray,
    lon_deg: np.ndarray,
    lat_deg: np.ndarray,
) -> np.ndarray:
    """Orient every spherical triangular element counter-clockwise.

    Parameters
    ----------
    connectivity
        Local zero-based triangular connectivity of shape ``(n, 3)``.
    lon_deg
        Node longitudes in degrees.
    lat_deg
        Node latitudes in degrees.

    Returns
    -------
    numpy.ndarray
        Connectivity with each element outward-facing/counter-clockwise.

    Raises
    ------
    ValueError
        If a degenerate spherical triangle is found.
    """
    xyz = unit_vectors(lon_deg, lat_deg)
    a = xyz[connectivity[:, 0]]
    b = xyz[connectivity[:, 1]]
    c = xyz[connectivity[:, 2]]
    sign = np.einsum("ij,ij->i", a, np.cross(b, c))
    if np.any(np.isclose(sign, 0.0, atol=1.0e-14)):
        raise ValueError("Foram encontrados triângulos degenerados em cellsOnVertex.")

    result = connectivity.copy()
    reverse = sign < 0.0
    result[reverse, 1] = connectivity[reverse, 2]
    result[reverse, 2] = connectivity[reverse, 1]
    return result


def unit_vectors(lon_deg: np.ndarray, lat_deg: np.ndarray) -> np.ndarray:
    """Convert geographic coordinates in degrees to three-dimensional unit vectors.

    Parameters
    ----------
    lon_deg
        Longitude values in degrees.
    lat_deg
        Latitude values in degrees.

    Returns
    -------
    numpy.ndarray
        Array with shape ``(n, 3)``.
    """
    lon = np.deg2rad(lon_deg)
    lat = np.deg2rad(lat_deg)
    return np.column_stack(
        (
            np.cos(lat) * np.cos(lon),
            np.cos(lat) * np.sin(lon),
            np.sin(lat),
        )
    )


def _netcdf_dataset() -> Any:
    try:
        from netCDF4 import Dataset
    except ImportError as exc:
        raise DependencyError(
            "A dependência 'netCDF4' não está disponível. "
            "Instale-a com conda/pip antes de gerar os pesos."
        ) from exc
    return Dataset


def _normalize_connectivity_shape(connectivity: np.ndarray) -> np.ndarray:
    if connectivity.ndim != 2:
        raise ValueError("cellsOnVertex deve ser bidimensional.")
    if connectivity.shape[1] != 3 and connectivity.shape[0] == 3:
        connectivity = connectivity.T
    if connectivity.shape[1] != 3:
        raise ValueError(
            "cellsOnVertex deve ter forma (nVertices, 3), "
            f"não {connectivity.shape}."
        )
    return connectivity


def _validate_connectivity(connectivity: np.ndarray, n_cells: int) -> np.ndarray:
    result = np.asarray(connectivity, dtype=np.int64)
    if np.any(result <= 0):
        raise ValueError(
            "cellsOnVertex contém índices de borda/inválidos. "
            "Esta versão requer uma malha MPAS global fechada."
        )
    result -= 1
    if np.any(result >= n_cells):
        raise ValueError("cellsOnVertex contém índice maior que nCells.")
    if np.any(np.diff(np.sort(result, axis=1), axis=1) == 0):
        raise ValueError("cellsOnVertex contém um triângulo com nó repetido.")
    return result


def _legacy_r2d_value_if_used(
    units: str,
    conversion: str,
    dtype: np.dtype[Any],
) -> float | None:
    if units != "radians" or conversion != "ncl_legacy" or dtype != np.dtype(np.float32):
        return None
    return float(
        np.float32(
            np.float32(180.0) / (np.arctan(np.float32(1.0)) * np.float32(4.0))
        )
    )
