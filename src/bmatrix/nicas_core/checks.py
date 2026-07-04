"""Validation of NICAS split and merged outputs."""
from __future__ import annotations

from pathlib import Path

from ..artifacts import read_manifest
from ..vbal_core.validate import validate_ranked_products


def _variables(workspace: str | Path) -> tuple[str, ...]:
    raw = read_manifest(workspace, expected_stage="nicas").metadata.get("variables", [])
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        return ()
    return tuple(raw)


def home_failure_files(run_dir: Path) -> list[Path]:
    """Return stale PBS files indicating a transient HOME/chdir failure."""
    return sorted(
        {
            path
            for pattern in ("*.o*", "*.e*")
            for path in run_dir.glob(pattern)
            if path.is_file() and "Could not chdir to home directory" in path.read_text(errors="replace")
        }
    )


def variable_errors(run_dir: Path) -> list[str]:
    """Collect structural errors for one NICAS variable workspace."""
    runlog = run_dir / "run_nicas.runlog"
    text = runlog.read_text(errors="replace") if runlog.is_file() else ""
    errors = []
    if "Finishing oops::ErrorCovarianceToolbox<MPAS> with status = 0" not in text:
        errors.append("status final de sucesso ausente")
    for name in ("mpas_nicas.nc", "mpas.nicas_norm.nc", "mpas.dirac_nicas.nc"):
        if not (run_dir / name).is_file():
            errors.append(f"produto ausente: {name}")
    errors.extend(validate_ranked_products(sorted(run_dir.glob("mpas_nicas_local_*")), "mpas_nicas_local"))
    errors.extend(validate_ranked_products(sorted(run_dir.glob("mpas_nicas_grids_local_*")), "mpas_nicas_grids_local"))
    return errors


def check(workspace: str | Path) -> bool:
    """Validate all configured NICAS controls and merged global products."""
    root = Path(workspace)
    variables = _variables(root)
    if not variables:
        raise RuntimeError("Manifesto NICAS não contém variáveis para validar.")
    errors: list[str] = []
    for variable in variables:
        run_dir = root / variable
        errors.extend(f"{variable}: {error}" for error in variable_errors(run_dir))
    merge_dir = root / "merge"
    for name in ("merge.done", "mpas_nicas.nc", "mpas.nicas_norm.nc", "mpas.dirac_nicas.nc"):
        if not (merge_dir / name).is_file():
            errors.append(f"merge: produto ausente: {name}")
    errors.extend(f"merge: {error}" for error in validate_ranked_products(sorted(merge_dir.glob("mpas_nicas_local_*")), "mpas_nicas_local"))
    errors.extend(f"merge: {error}" for error in validate_ranked_products(sorted(merge_dir.glob("mpas_nicas_grids_local_*")), "mpas_nicas_grids_local"))
    if errors:
        raise RuntimeError("NICAS falhou ou ficou incompleto: " + "; ".join(errors))
    return True
