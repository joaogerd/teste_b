"""ESMPy dependency loading and geometry construction."""

from __future__ import annotations

from typing import Any

import numpy as np

from .config import WeightGenerationConfig
from .errors import ConfigurationError, DependencyError
from .mpas import MpasMeshData


def get_esmf() -> Any:
    """Import and return the installed ESMPy module.

    Returns
    -------
    module
        The ESMPy module, imported as ``esmpy`` or legacy ``ESMF``.

    Raises
    ------
    DependencyError
        If neither import name is available.
    """
    try:
        import esmpy as ESMF
    except ImportError:
        try:
            import ESMF  # type: ignore[import-not-found]
        except ImportError as exc:
            raise DependencyError(
                "ESMPy/ESMF não está disponível. Instale 'esmpy' no ambiente "
                "conda antes de gerar os pesos."
            ) from exc
    return ESMF


def initialize_esmf(*, debug: bool) -> Any:
    """Create the ESMF manager and reject distributed execution.

    Parameters
    ----------
    debug
        Whether ESMF debug logging should be enabled.

    Returns
    -------
    module
        Imported ESMF module.

    Raises
    ------
    RuntimeError
        If the process belongs to a multi-PET ESMF execution.
    DependencyError
        If ESMPy is not installed.
    """
    ESMF = get_esmf()
    ESMF.Manager(debug=debug)
    if ESMF.pet_count() != 1:
        raise RuntimeError(
            "Esta versão requer execução serial. Não use mpiexec; "
            "gere os pesos em um único processo."
        )
    return ESMF


def regular_axis(start: float, stop: float, step: float, axis_name: str) -> np.ndarray:
    """Build a regular inclusive coordinate axis.

    Parameters
    ----------
    start
        First coordinate.
    stop
        Last coordinate.
    step
        Positive coordinate increment.
    axis_name
        Human-readable axis name used in validation errors.

    Returns
    -------
    numpy.ndarray
        Float64 inclusive regular axis.

    Raises
    ------
    ConfigurationError
        If the range is not exactly divisible by the provided increment.
    """
    count_float = (stop - start) / step + 1.0
    count = int(round(count_float))
    if count < 2 or not np.isclose(count_float, count, atol=1.0e-10, rtol=0.0):
        raise ConfigurationError(
            f"Eixo {axis_name} não é divisível pela resolução fornecida."
        )
    return np.linspace(start, stop, count, dtype=np.float64)


def make_latlon_grid(config: WeightGenerationConfig, ESMF: Any) -> tuple[Any, int, int]:
    """Construct the periodic regular latitude–longitude ESMF grid.

    Parameters
    ----------
    config
        Validated generation configuration.
    ESMF
        Imported ESMPy module.

    Returns
    -------
    tuple
        ``(grid, nlat, nlon)`` where ``grid`` is the ESMF grid.

    Notes
    -----
    The grid uses centered coordinates, one periodic longitude dimension, and
    a pole dimension as in the original script.
    """
    lat_axis = regular_axis(
        config.ll_corner[0], config.ur_corner[0], config.resolution_deg, "latitude"
    )
    lon_axis = regular_axis(
        config.ll_corner[1], config.ur_corner[1], config.resolution_deg, "longitude"
    )
    nlat, nlon = lat_axis.size, lon_axis.size

    grid = ESMF.Grid(
        max_index=np.asarray([nlon, nlat], dtype=np.int32),
        coord_sys=ESMF.CoordSys.SPH_DEG,
        staggerloc=ESMF.StaggerLoc.CENTER,
        num_peri_dims=1,
        periodic_dim=0,
        pole_dim=1,
    )
    lon = grid.get_coords(0, staggerloc=ESMF.StaggerLoc.CENTER)
    lat = grid.get_coords(1, staggerloc=ESMF.StaggerLoc.CENTER)
    lon[...] = lon_axis[:, np.newaxis]
    lat[...] = lat_axis[np.newaxis, :]
    return grid, int(nlat), int(nlon)


def make_mpas_dual_mesh(mesh_data: MpasMeshData, ESMF: Any) -> Any:
    """Construct an ESMF mesh from MPAS dual-mesh data.

    Parameters
    ----------
    mesh_data
        Validated MPAS coordinates and local triangular connectivity.
    ESMF
        Imported ESMPy module.

    Returns
    -------
    object
        Configured ESMPy mesh.

    Raises
    ------
    ValueError
        If local connectivity is inconsistent with the node set.

    Notes
    -----
    ESMPy expects zero-based **local indices** in ``add_elements`` connectivity,
    even when node IDs themselves are one-based. The MPAS data stored in
    :class:`~bmatrix.esmf_weights.mpas.MpasMeshData` already has this required
    representation.
    """
    node_count = mesh_data.n_cells
    element_count = mesh_data.n_triangles
    mesh = ESMF.Mesh(
        parametric_dim=2,
        spatial_dim=2,
        coord_sys=ESMF.CoordSys.SPH_DEG,
    )

    node_ids = np.arange(1, node_count + 1, dtype=np.int32)
    node_owners = np.zeros(node_count, dtype=np.int32)
    node_coords = np.column_stack((mesh_data.lon_deg, mesh_data.lat_deg))
    mesh.add_nodes(
        node_count,
        node_ids,
        node_coords.astype(np.float64).ravel(),
        node_owners,
    )

    element_connectivity = mesh_data.connectivity.astype(np.int32).ravel()
    if element_connectivity.size != element_count * 3:
        raise ValueError("Conectividade triangular inválida para ESMF.Mesh.")
    if (
        element_connectivity.size == 0
        or element_connectivity.min() < 0
        or element_connectivity.max() >= node_count
    ):
        raise ValueError(
            "Conectividade local fora do intervalo [0, nCells-1]: "
            f"min={element_connectivity.min() if element_connectivity.size else 'N/A'}, "
            f"max={element_connectivity.max() if element_connectivity.size else 'N/A'}, "
            f"nCells={node_count}."
        )

    element_ids = np.arange(1, element_count + 1, dtype=np.int32)
    element_types = np.full(element_count, ESMF.MeshElemType.TRI, dtype=np.int32)
    element_lon = np.mean(mesh_data.lon_deg[mesh_data.connectivity], axis=1)
    element_lat = np.mean(mesh_data.lat_deg[mesh_data.connectivity], axis=1)
    element_coords = np.column_stack((element_lon, element_lat)).astype(np.float64).ravel()

    mesh.add_elements(
        element_count,
        element_ids,
        element_types,
        element_connectivity,
        element_coords=element_coords,
    )
    return mesh
