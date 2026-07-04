"""Configuration model and YAML loading for MPAS ESMF weight generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import yaml


from .errors import ConfigurationError
from .utils import resolution_tag


@dataclass(frozen=True, slots=True)
class WeightGenerationConfig:
    """Validated configuration for a complete ESMF weight-generation run.

    Parameters
    ----------
    mpas_file
        Path to the MPAS NetCDF mesh file.
    mpas_grid_id
        Identifier used in generated filenames and the manifest.
    lat_var
        NetCDF variable holding MPAS cell latitudes.
    lon_var
        NetCDF variable holding MPAS cell longitudes.
    connectivity_var
        NetCDF variable holding triangular MPAS dual-mesh connectivity.
    coordinate_units
        Coordinate-unit policy: ``"auto"``, ``"radians"``, or ``"degrees"``.
    coordinate_conversion
        Conversion policy for radians: ``"ncl_legacy"`` or ``"double"``.
    resolution_deg
        Regular latitude–longitude grid resolution in degrees.
    ll_corner
        Lower-left grid-center coordinate as ``(latitude, longitude)``.
    ur_corner
        Upper-right grid-center coordinate as ``(latitude, longitude)``.
    latlon_grid_id
        Identifier used in generated filenames and the manifest.
    output_dir
        Directory where weights and the manifest will be written.
    force
        Whether existing output files may be replaced.
    debug
        Whether to activate ESMF debug mode.

    Notes
    -----
    Instances are immutable. Construct them directly in Python or obtain one
    from :func:`load_config`.
    """

    mpas_file: Path
    mpas_grid_id: str
    lat_var: str
    lon_var: str
    connectivity_var: str
    coordinate_units: str
    coordinate_conversion: str
    resolution_deg: float
    ll_corner: tuple[float, float]
    ur_corner: tuple[float, float]
    latlon_grid_id: str
    output_dir: Path
    force: bool = False
    debug: bool = False

    def output_paths(self) -> tuple[Path, Path]:
        """Return the deterministic paths of both ESMF weight files.

        Returns
        -------
        tuple[pathlib.Path, pathlib.Path]
            Paths in the order ``(latlon_to_mpas, mpas_to_latlon)``.

        Examples
        --------
        >>> from pathlib import Path
        >>> config = WeightGenerationConfig(
        ...     mpas_file=Path("mesh.nc"), mpas_grid_id="x1",
        ...     lat_var="latCell", lon_var="lonCell",
        ...     connectivity_var="cellsOnVertex",
        ...     coordinate_units="auto", coordinate_conversion="ncl_legacy",
        ...     resolution_deg=1.0, ll_corner=(-89.5, -179.5),
        ...     ur_corner=(89.5, 179.5), latlon_grid_id="latlon_1p0",
        ...     output_dir=Path("weights"),
        ... )
        >>> [path.name for path in config.output_paths()]
        ['latlon_1p0_to_MPAS_x1_bilinear.nc', 'MPAS_x1_to_latlon_1p0_bilinear.nc']
        """
        forward = self.output_dir / (
            f"{self.latlon_grid_id}_to_MPAS_{self.mpas_grid_id}_bilinear.nc"
        )
        reverse = self.output_dir / (
            f"MPAS_{self.mpas_grid_id}_to_{self.latlon_grid_id}_bilinear.nc"
        )
        return forward, reverse


def load_config(
    path: Path,
    *,
    force_override: bool = False,
    debug_override: bool = False,
) -> WeightGenerationConfig:
    """Load and validate a YAML configuration file.

    Relative paths in the YAML file are resolved from the directory containing
    the configuration file, not from the process working directory.

    Parameters
    ----------
    path
        YAML configuration file.
    force_override
        When ``True``, force replacement of existing output files independently
        of ``output.force`` in YAML.
    debug_override
        When ``True``, enable ESMF debug mode independently of ``esmf.debug``
        in YAML.

    Returns
    -------
    WeightGenerationConfig
        Fully validated configuration object.

    Raises
    ------
    ConfigurationError
        If the file cannot be read, is invalid YAML, contains invalid
        internal variables, or does not meet the expected configuration
        contract.

    Examples
    --------
    >>> from pathlib import Path
    >>> config = load_config(Path("generate_esmf_weights.yaml"))
    >>> config.resolution_deg > 0
    True
    """
    path = Path(path).expanduser().resolve()
    try:
        raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(
            f"Não foi possível ler a configuração '{path}': {exc}"
        ) from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"YAML inválido em '{path}': {exc}") from exc

    if raw_data is None:
        raise ConfigurationError(f"O arquivo YAML está vazio: {path}.")

    if not isinstance(raw_data, Mapping):
        raise ConfigurationError(
            "A raiz do arquivo YAML deve ser um bloco de mapeamento."
        )

    data = _render_variables(raw_data)

    root = _as_mapping(data, "raiz")
    mpas = _as_mapping(root.get("mpas"), "mpas")
    latlon = _as_mapping(root.get("latlon"), "latlon")
    output = _as_mapping(root.get("output"), "output")
    esmf = _as_mapping(root.get("esmf", {}), "esmf")

    base_dir = path.parent
    mpas_file = _required_path(mpas, "file", base_dir, "mpas.file")
    mpas_grid_id = _required_nonempty_string(mpas, "grid_id", "mpas.grid_id")

    coordinate_units = str(mpas.get("coordinate_units", "auto")).strip().lower()
    if coordinate_units not in {"auto", "radians", "degrees"}:
        raise ConfigurationError(
            "mpas.coordinate_units deve ser um de: auto, radians, degrees."
        )

    coordinate_conversion = str(
        mpas.get("coordinate_conversion", "ncl_legacy")
    ).strip().lower()
    if coordinate_conversion not in {"ncl_legacy", "double"}:
        raise ConfigurationError(
            "mpas.coordinate_conversion deve ser um de: ncl_legacy, double."
        )

    resolution_deg = _positive_finite_float(
        latlon.get("resolution_deg"), "latlon.resolution_deg"
    )
    default_ll = [-90.0 + resolution_deg / 2.0, -180.0 + resolution_deg / 2.0]
    default_ur = [90.0 - resolution_deg / 2.0, 180.0 - resolution_deg / 2.0]
    ll_corner = _coordinate_pair(latlon.get("ll_corner", default_ll), "latlon.ll_corner")
    ur_corner = _coordinate_pair(latlon.get("ur_corner", default_ur), "latlon.ur_corner")
    if ur_corner[0] <= ll_corner[0] or ur_corner[1] <= ll_corner[1]:
        raise ConfigurationError(
            "latlon.ll_corner e latlon.ur_corner devem definir uma área crescente."
        )

    latlon_grid_id = str(
        latlon.get("grid_id", f"latlon_{resolution_tag(resolution_deg)}")
    ).strip()
    if not latlon_grid_id:
        raise ConfigurationError("latlon.grid_id não pode ser vazio.")

    output_dir = _required_path(output, "directory", base_dir, "output.directory")
    forward, reverse = _output_paths(output_dir, latlon_grid_id, mpas_grid_id)
    if forward == reverse:
        raise ConfigurationError(
            "Os identificadores de grade gerariam nomes de arquivos de peso idênticos."
        )

    return WeightGenerationConfig(
        mpas_file=mpas_file,
        mpas_grid_id=mpas_grid_id,
        lat_var=_optional_nonempty_string(mpas, "lat_var", "latCell", "mpas.lat_var"),
        lon_var=_optional_nonempty_string(mpas, "lon_var", "lonCell", "mpas.lon_var"),
        connectivity_var=_optional_nonempty_string(
            mpas, "connectivity_var", "cellsOnVertex", "mpas.connectivity_var"
        ),
        coordinate_units=coordinate_units,
        coordinate_conversion=coordinate_conversion,
        resolution_deg=resolution_deg,
        ll_corner=ll_corner,
        ur_corner=ur_corner,
        latlon_grid_id=latlon_grid_id,
        output_dir=output_dir,
        force=bool(output.get("force", False) or force_override),
        debug=bool(esmf.get("debug", False) or debug_override),
    )



def from_bmatrix_config(
    config: Mapping[str, Any],
    *,
    output_dir: Path,
    force: bool = False,
    debug: bool = False,
) -> WeightGenerationConfig:
    """Build validated ESMF settings from the B-matrix scientific contract.

    Parameters
    ----------
    config
        Fully merged B-matrix configuration.  The function consumes
        ``mesh`` and ``bflow.regridding`` only; it does not require a second
        YAML file or a separate executable.
    output_dir
        Workspace-local directory where weight files and provenance are written.
    force
        Replace existing weight files.
    debug
        Enable ESMF debug logging.

    Returns
    -------
    WeightGenerationConfig
        Immutable, validated generation settings.
    """
    mesh = _as_mapping(config.get("mesh"), "mesh")
    bflow = _as_mapping(config.get("bflow"), "bflow")
    regridding = _as_mapping(bflow.get("regridding"), "bflow.regridding")

    resolution = regridding.get("resolution_deg", regridding.get("latlon_resolution_deg"))
    if resolution is None:
        legacy = str(regridding.get("scrip_resolution", "")).strip().lower()
        if legacy.endswith("deg"):
            resolution = legacy[:-3]
    resolution_deg = _positive_finite_float(resolution, "bflow.regridding.resolution_deg")
    lower_left = regridding.get("lower_left", [-90.0 + resolution_deg / 2.0, -180.0 + resolution_deg / 2.0])
    upper_right = regridding.get("upper_right", [90.0 - resolution_deg / 2.0, 180.0 - resolution_deg / 2.0])

    mpas_file = Path(_required_nonempty_string(mesh, "grid", "mesh.grid")).expanduser()
    grid_id = _optional_nonempty_string(mesh, "name", "mpas", "mesh.name")
    output_dir = Path(output_dir).expanduser().resolve()
    latlon_id = str(regridding.get("latlon_grid_id", f"latlon_{resolution_tag(resolution_deg)}")).strip()
    if not latlon_id:
        raise ConfigurationError("bflow.regridding.latlon_grid_id não pode ser vazio.")

    coordinate_units = str(regridding.get("coordinate_units", "auto")).strip().lower()
    if coordinate_units not in {"auto", "radians", "degrees"}:
        raise ConfigurationError(
            "bflow.regridding.coordinate_units deve ser auto, radians ou degrees."
        )
    coordinate_conversion = str(regridding.get("coordinate_conversion", "ncl_legacy")).strip().lower()
    if coordinate_conversion not in {"ncl_legacy", "double"}:
        raise ConfigurationError(
            "bflow.regridding.coordinate_conversion deve ser ncl_legacy ou double."
        )
    ll_corner = _coordinate_pair(lower_left, "bflow.regridding.lower_left")
    ur_corner = _coordinate_pair(upper_right, "bflow.regridding.upper_right")
    if ur_corner[0] <= ll_corner[0] or ur_corner[1] <= ll_corner[1]:
        raise ConfigurationError(
            "bflow.regridding.lower_left e upper_right devem definir uma área crescente."
        )

    return WeightGenerationConfig(
        mpas_file=mpas_file,
        mpas_grid_id=grid_id,
        lat_var=_optional_nonempty_string(regridding, "lat_var", "latCell", "bflow.regridding.lat_var"),
        lon_var=_optional_nonempty_string(regridding, "lon_var", "lonCell", "bflow.regridding.lon_var"),
        connectivity_var=_optional_nonempty_string(
            regridding, "connectivity_var", "cellsOnVertex", "bflow.regridding.connectivity_var"
        ),
        coordinate_units=coordinate_units,
        coordinate_conversion=coordinate_conversion,
        resolution_deg=resolution_deg,
        ll_corner=ll_corner,
        ur_corner=ur_corner,
        latlon_grid_id=latlon_id,
        output_dir=output_dir,
        force=force,
        debug=debug or bool(regridding.get("debug", False)),
    )


def _render_variables(value: Any, root: Mapping[str, Any] | None = None) -> Any:
    """Render environment variables and simple ``{root_key}`` references.

    The function deliberately supports only deterministic substitutions.  It
    keeps the ESMF adapter independent from any external configuration package.
    """
    import os

    root = value if root is None and isinstance(value, Mapping) else root
    if isinstance(value, Mapping):
        return {key: _render_variables(item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [_render_variables(item, root) for item in value]
    if isinstance(value, str):
        rendered = os.path.expandvars(value)
        if isinstance(root, Mapping):
            scalar_values = {key: item for key, item in root.items() if isinstance(item, (str, int, float))}
            try:
                rendered = rendered.format(**scalar_values)
            except KeyError:
                pass
        return rendered
    return value

def _output_paths(output_dir: Path, latlon_id: str, mpas_id: str) -> tuple[Path, Path]:
    return (
        output_dir / f"{latlon_id}_to_MPAS_{mpas_id}_bilinear.nc",
        output_dir / f"MPAS_{mpas_id}_to_{latlon_id}_bilinear.nc",
    )


def _as_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"'{name}' deve ser um bloco YAML (mapeamento).")
    return value


def _required_nonempty_string(mapping: Mapping[str, Any], key: str, name: str) -> str:
    value = str(mapping.get(key, "")).strip()
    if not value:
        raise ConfigurationError(f"{name} é obrigatório e não pode ser vazio.")
    return value


def _optional_nonempty_string(
    mapping: Mapping[str, Any], key: str, default: str, name: str
) -> str:
    value = str(mapping.get(key, default)).strip()
    if not value:
        raise ConfigurationError(f"{name} não pode ser vazio.")
    return value


def _required_path(
    mapping: Mapping[str, Any], key: str, base_dir: Path, name: str
) -> Path:
    raw_value = _required_nonempty_string(mapping, key, name)
    path = Path(raw_value).expanduser()
    return path if path.is_absolute() else (base_dir / path).resolve()


def _positive_finite_float(value: Any, name: str) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} deve ser um número positivo.") from exc
    if not np.isfinite(converted) or converted <= 0.0:
        raise ConfigurationError(f"{name} deve ser um número finito positivo.")
    return converted


def _coordinate_pair(value: Any, name: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ConfigurationError(f"{name} deve ser [latitude, longitude].")
    try:
        latitude, longitude = float(value[0]), float(value[1])
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} deve conter valores numéricos.") from exc
    if not (np.isfinite(latitude) and np.isfinite(longitude)):
        raise ConfigurationError(f"{name} deve conter valores finitos.")
    return latitude, longitude
