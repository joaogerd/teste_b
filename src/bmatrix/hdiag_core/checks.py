from __future__ import annotations

from pathlib import Path


def check(workspace: str | Path) -> bool:
    root = Path(workspace)
    run_dir = root / "HDIAG"
    log = run_dir / "run_hdiag.runlog"
    text = log.read_text(errors="replace") if log.is_file() else ""
    errors = []
    if not log.is_file():
        errors.append("run_hdiag.runlog ausente")
    if "Finishing oops::ErrorCovarianceToolbox<MPAS> with status = 0" not in text:
        errors.append("status final de sucesso ausente no run_hdiag.runlog")
    for name in ["mpas.stddev.nc", "mpas.cor_rh.nc", "mpas.cor_rv.nc"]:
        if not (run_dir / name).is_file():
            errors.append(f"produto HDIAG ausente: {name}")

    print("=== HDIAG validation ===")
    print(f"WORKSPACE={root}")
    if errors:
        for error in errors:
            print(f"  - {error}")
        print_diagnostics(root)
        raise SystemExit("ERRO: HDIAG falhou ou ficou incompleto.")
    print("SUCCESS: HDIAG validado.")
    return True


def print_diagnostics(workspace: Path, tail_lines: int = 80) -> None:
    run_dir = workspace / "HDIAG"
    print("=== HDIAG diagnostics ===")
    for name in ["stdout.log", "stderr.log", "run_hdiag.runlog", "log.atmosphere.0000.err"]:
        path = run_dir / name
        print(f"--- {path} (ultimas {tail_lines} linhas) ---")
        if not path.is_file():
            print("[arquivo ausente]")
            continue
        lines = path.read_text(errors="replace").splitlines()
        print("\n".join(lines[-tail_lines:]) or "[arquivo vazio]")

    stdout = run_dir / "stdout.log"
    if stdout.is_file() and "ens_ne/ens_nsub should be larger than 3" in stdout.read_text(errors="replace"):
        print("CAUSA IDENTIFICADA: BUMP_NICAS requer pelo menos 4 membros por sub-ensemble.")
