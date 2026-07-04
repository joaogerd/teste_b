from __future__ import annotations

import re
from pathlib import Path

from .model import so_artifacts


def so_errors(run_dir: Path, variant: str = "default") -> list[str]:
    artifacts = so_artifacts(variant)
    runlog = run_dir / artifacts["runlog"]
    text = runlog.read_text(errors="replace") if runlog.is_file() else ""
    errors = []
    if "with status = 0" not in text:
        errors.append(f"status final de sucesso ausente no {artifacts['runlog']}")
    if not list(run_dir.glob("an.*.nc")):
        errors.append("arquivo de análise an.*.nc ausente")
    expected_obs = {
        "default": ["obsout_SO_T.h5", "obsout_SO_U.h5"],
        "t-only": ["obsout_SO_T.h5"],
        "u-only": ["obsout_SO_U.h5"],
    }
    for name in expected_obs[variant]:
        if not (run_dir / name).is_file():
            errors.append(f"produto SO ausente: {name}")
    combined = "\n".join(
        path.read_text(errors="replace")
        for path in [runlog, run_dir / artifacts["stdout"], run_dir / artifacts["stderr"]]
        if path.is_file()
    )
    nonzero_statuses = re.findall(r"with status\s*=\s*(-?\d+)", combined)
    if any(status != "0" for status in nonzero_statuses):
        errors.append("status final diferente de zero encontrado nos logs")
    return errors


def check(workspace: str | Path, variant: str = "default") -> bool:
    root = Path(workspace)
    errors = so_errors(root, variant=variant)
    print("=== SO validation ===")
    print(f"WORKSPACE={root}")
    print(f"VARIANT={variant}")
    if errors:
        for error in errors:
            print(f"  - {error}")
        raise SystemExit("ERRO: SO falhou ou ficou incompleto.")
    print("SUCCESS: SO validado.")
    return True
