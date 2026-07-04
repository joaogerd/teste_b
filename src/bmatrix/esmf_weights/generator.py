"""Reusable orchestration for generating MPAS <-> lat-lon ESMF weights."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import WeightGenerationConfig
from .esmf_support import initialize_esmf, make_latlon_grid, make_mpas_dual_mesh
from .mpas import read_mpas_mesh
from .output import WeightValidation, validate_weight_file, write_manifest

ProgressReporter = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """Artifacts and metadata produced by :func:`generate_weights`.

    Parameters
    ----------
    forward_weights
        Weight file interpolating regular lat-lon data to MPAS cells.
    reverse_weights
        Weight file interpolating MPAS cell data to the regular lat-lon grid.
    manifest
        JSON provenance manifest.
    forward_validation
        Validation summary for `forward_weights`.
    reverse_validation
        Validation summary for `reverse_weights`.
    n_cells
        Number of MPAS cells.
    n_triangles
        Number of MPAS dual-mesh triangular elements.
    latlon_shape
        Shape of the regular grid as ``(nlat, nlon)``.
    """

    forward_weights: Path
    reverse_weights: Path
    manifest: Path
    forward_validation: WeightValidation
    reverse_validation: WeightValidation
    n_cells: int
    n_triangles: int
    latlon_shape: tuple[int, int]


def generate_weights(
    config: WeightGenerationConfig,
    *,
    progress: ProgressReporter | None = None,
) -> GenerationResult:
    """Generate, validate, and document both MPAS/lat-lon ESMF weight files.

    This is the library entry point. It does not parse command-line arguments
    and does not print. Supply `progress=print` or another callback when
    execution status should be reported.

    Parameters
    ----------
    config
        Fully validated generation configuration, usually returned by
        :func:`bflow.preprocessing.esmf_weights.load_config`.
    progress
        Optional callback called with human-readable progress messages.

    Returns
    -------
    GenerationResult
        Paths, validation summaries, and geometry dimensions of the completed
        run.

    Raises
    ------
    FileExistsError
        If an output file already exists and ``config.force`` is false.
    FileNotFoundError
        If the MPAS mesh file does not exist.
    RuntimeError
        If generation is launched with more than one ESMF PET.
    ValueError
        If configuration-derived geometry or the MPAS mesh is invalid.
    OSError
        If output files cannot be created or written.

    Examples
    --------
    >>> from pathlib import Path
    >>> from bmatrix.esmf_weights import generate_weights, load_config
    >>> config = load_config(Path("generate_esmf_weights.yaml"))
    >>> result = generate_weights(config, progress=print)
    >>> result.manifest.name
    'weights_manifest.json'
    """
    _emit(progress, "Lendo MPAS e construindo a malha dual...")
    mesh_data = read_mpas_mesh(config)
    _emit(progress, f"  nCells: {mesh_data.n_cells}")
    _emit(progress, f"  elementos triangulares: {mesh_data.n_triangles}")
    _emit(
        progress,
        "  conversão angular: "
        f"{mesh_data.metadata['coordinate_conversion']} "
        f"({mesh_data.metadata['input_dtype']})",
    )

    config.output_dir.mkdir(parents=True, exist_ok=True)
    forward_path, reverse_path = config.output_paths()
    _prepare_output_paths((forward_path, reverse_path), force=config.force)

    ESMF = initialize_esmf(debug=config.debug)
    grid, nlat, nlon = make_latlon_grid(config, ESMF)
    mpas_mesh = make_mpas_dual_mesh(mesh_data, ESMF)
    grid_field = ESMF.Field(
        grid,
        name="latlon",
        staggerloc=ESMF.StaggerLoc.CENTER,
    )
    mesh_field = ESMF.Field(
        mpas_mesh,
        name="mpas_cell",
        meshloc=ESMF.MeshLoc.NODE,
    )

    common_options = {
        "regrid_method": ESMF.RegridMethod.BILINEAR,
        "line_type": ESMF.LineType.CART,
        "norm_type": ESMF.NormType.DSTAREA,
        "unmapped_action": ESMF.UnmappedAction.IGNORE,
        "ignore_degenerate": True,
        "large_file": True,
    }

    _emit(progress, "Gerando pesos latlon -> MPAS com ESMPy...")
    _write_weights(
        ESMF,
        srcfield=grid_field,
        dstfield=mesh_field,
        filename=forward_path,
        pole_method=ESMF.PoleMethod.ALLAVG,
        options=common_options,
    )

    _emit(progress, "Gerando pesos MPAS -> latlon com ESMPy...")
    _write_weights(
        ESMF,
        srcfield=mesh_field,
        dstfield=grid_field,
        filename=reverse_path,
        options=common_options,
    )

    forward_validation = validate_weight_file(forward_path)
    reverse_validation = validate_weight_file(reverse_path)
    for validation in (forward_validation, reverse_validation):
        _emit(
            progress,
            f"  {validation.path.name}: {validation.entries} pesos, "
            f"erro máximo de soma={validation.max_abs_row_sum_error:.3e}",
        )

    manifest = write_manifest(
        config,
        (forward_path, reverse_path),
        nlat=nlat,
        nlon=nlon,
        mesh_data=mesh_data,
        validation=(forward_validation, reverse_validation),
    )
    _emit(progress, "Concluído.")
    _emit(progress, f"  {forward_path}")
    _emit(progress, f"  {reverse_path}")
    _emit(progress, f"  {manifest}")

    return GenerationResult(
        forward_weights=forward_path,
        reverse_weights=reverse_path,
        manifest=manifest,
        forward_validation=forward_validation,
        reverse_validation=reverse_validation,
        n_cells=mesh_data.n_cells,
        n_triangles=mesh_data.n_triangles,
        latlon_shape=(nlat, nlon),
    )


def _prepare_output_paths(paths: tuple[Path, ...], *, force: bool) -> None:
    existing = tuple(path for path in paths if path.exists())
    if existing and not force:
        listing = ", ".join(str(path) for path in existing)
        raise FileExistsError(
            "Arquivo(s) de peso já existente(s): "
            f"{listing}. Use --force ou output.force: true."
        )
    for path in existing:
        path.unlink()


def _write_weights(
    ESMF: object,
    *,
    srcfield: object,
    dstfield: object,
    filename: Path,
    pole_method: object | None = None,
    options: dict[str, object],
) -> None:
    kwargs: dict[str, object] = {
        "srcfield": srcfield,
        "dstfield": dstfield,
        "filename": str(filename),
        **options,
    }
    if pole_method is not None:
        kwargs["pole_method"] = pole_method

    regrid = ESMF.Regrid(**kwargs)  # type: ignore[attr-defined]
    try:
        # Constructing Regrid with filename writes the sparse weight file.
        pass
    finally:
        regrid.destroy()


def _emit(progress: ProgressReporter | None, message: str) -> None:
    if progress is not None:
        progress(message)
