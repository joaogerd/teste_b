from __future__ import annotations

import re
from pathlib import Path

from ..artifacts import read_manifest


def _sample_stem(root: Path) -> str:
    manifest = read_manifest(root, expected_stage="vbal")
    value = manifest.metadata.get("sample_stem")
    if not isinstance(value, str) or not value:
        raise RuntimeError("Manifesto VBAL não contém sample_stem.")
    return value


def validate(workspace: str | Path) -> bool:
    """Validate VBAL products, logs and configured unbalanced samples."""
    root = Path(workspace)
    run_dir = root / "VBAL"
    stem = _sample_stem(root)
    log = run_dir / "run_vbal.runlog"
    text = log.read_text(errors="replace") if log.is_file() else ""

    bad_tokens = ["ABORT", "Exception", "Segmentation fault", "CRITICAL"]
    errors = [token for token in bad_tokens if token.lower() in text.lower()]
    global_products = [run_dir / "mpas_sampling.nc", run_dir / "mpas_vbal.nc"]
    sampling_local = sorted(run_dir.glob("mpas_sampling_local_*"))
    vbal_local = sorted(run_dir.glob("mpas_vbal_local_*"))
    original_outputs = sorted((root / "samples").glob(f"{stem}_*.nc"))

    if not log.is_file():
        errors.append("run_vbal.runlog ausente")
    if "Finishing oops::ErrorCovarianceToolbox<MPAS> with status = 0" not in text:
        errors.append("status final de sucesso ausente no run_vbal.runlog")
    for product in global_products:
        if not product.is_file():
            errors.append(f"produto VBAL ausente: {product.name}")
    errors.extend(validate_ranked_products(sampling_local, "mpas_sampling_local"))
    errors.extend(validate_ranked_products(vbal_local, "mpas_vbal_local"))
    if not original_outputs:
        errors.append(f"nenhuma amostra original encontrada em samples/{stem}_*.nc")

    print("=== VBAL validation ===")
    print(f"WORKSPACE={root}")
    print(f"RUNLOG={log}")
    print(f"SAMPLE_STEM={stem}")
    print(f"SAMPLING_GLOBAL={(run_dir / 'mpas_sampling.nc').is_file()}")
    print(f"VBAL_GLOBAL={(run_dir / 'mpas_vbal.nc').is_file()}")
    print(f"SAMPLING_LOCAL={len(sampling_local)}")
    print(f"VBAL_LOCAL={len(vbal_local)}")
    print(f"ORIGINAL_SAMPLES={len(original_outputs)}")

    if errors:
        print("Problemas:")
        for err in errors:
            print(f"  - {err}")
        print_diagnostics(root)
        raise RuntimeError("VBAL falhou ou ficou incompleto.")

    print("SUCCESS: VBAL validado.")
    return True


def validate_ranked_products(paths: list[Path], prefix: str) -> list[str]:
    """Validate expected MPI-rank output file naming."""
    if not paths:
        return [f"nenhum arquivo {prefix}_* foi gerado"]
    matches = [re.search(r"_local_(\d{6})-(\d{6})\.nc$", path.name) for path in paths]
    if any(match is None for match in matches):
        return [f"nome inesperado em arquivos {prefix}_*"]
    expected = int(matches[0].group(1))
    ranks = {int(match.group(2)) for match in matches if match}
    errors = []
    if len(paths) != expected:
        errors.append(f"{prefix}_* incompletos: esperados={expected}, gerados={len(paths)}")
    missing = sorted(set(range(1, expected + 1)) - ranks)
    if missing:
        errors.append(f"{prefix}_* ranks ausentes: {missing[:10]}")
    return errors


def print_diagnostics(workspace: Path, tail_lines: int = 80) -> None:
    """Print concise diagnostics after a failed VBAL validation."""
    run_dir = workspace / "VBAL"
    print("=== VBAL diagnostics ===")
    for name in ["stdout.log", "stderr.log", "run_vbal.runlog", "log.atmosphere.0000.err"]:
        path = run_dir / name
        print(f"--- {path} (ultimas {tail_lines} linhas) ---")
        if not path.is_file():
            print("[arquivo ausente]")
            continue
        lines = path.read_text(errors="replace").splitlines()
        print("\n".join(lines[-tail_lines:]) or "[arquivo vazio]")
