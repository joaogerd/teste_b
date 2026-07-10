from __future__ import annotations

import shutil
from pathlib import Path

from ..artifacts import StageManifest, read_manifest, write_manifest
from ..shell import write_text
from ..unbalance_core.checks import check as validate_unbalance
from ..vbal_core.model import vbal_date
from .config_files import write_hdiag_pbs, write_hdiag_yaml
from .model import hdiag_workspace, require_hdiag_members
from .static import link_hdiag_inputs


def _sample_stem(unbalance_root: Path) -> str:
    manifest = read_manifest(unbalance_root, expected_stage="unbalance")
    value = manifest.metadata.get("sample_stem")
    if not isinstance(value, str) or not value:
        raise RuntimeError("Manifesto UNBALANCE não contém sample_stem.")
    return value


def _vbal_root(unbalance_root: Path) -> Path:
    manifest = read_manifest(unbalance_root, expected_stage="unbalance")
    value = manifest.inputs.get("vbal_workspace")
    if not isinstance(value, str) or not value:
        raise RuntimeError("Manifesto UNBALANCE não contém vbal_workspace.")
    return Path(value)


def prepare(config, unbalance_workspace: str | Path, workspace: str | Path | None = None, clean: bool = False) -> Path:
    """Prepare HDIAG from validated K2^-1 samples produced by UNBALANCE."""
    unbalance_root = Path(unbalance_workspace)
    validate_unbalance(unbalance_root, config)
    vbal_root = _vbal_root(unbalance_root)
    sample_stem = _sample_stem(unbalance_root)
    samples = sorted((unbalance_root / "samplesUnbalanced").glob(f"{sample_stem}_*.nc"))
    if not samples:
        raise RuntimeError("Nenhuma amostra unbalanced encontrada no workspace UNBALANCE.")
    require_hdiag_members(samples, int(config.get("hdiag", {}).get("min_members", 4)))

    out = Path(workspace) if workspace else hdiag_workspace(config, unbalance_root)
    if clean and out.exists():
        shutil.rmtree(out)
    run_dir = out / "HDIAG"
    run_dir.mkdir(parents=True, exist_ok=True)

    link_hdiag_inputs(unbalance_root, vbal_root, out, run_dir)
    date = vbal_date(vbal_root)
    write_hdiag_yaml(config, run_dir / "run_hdiag.yaml", len(samples), date, sample_stem=sample_stem)
    write_hdiag_pbs(config, run_dir)
    write_manifest(
        StageManifest(
            stage="hdiag",
            workspace=str(out.resolve()),
            inputs={
                "unbalance_workspace": str(unbalance_root.resolve()),
                "vbal_workspace": str(vbal_root.resolve()),
            },
            outputs={
                "stddev": str((run_dir / "mpas.stddev.nc").resolve()),
                "cor_rh": str((run_dir / "mpas.cor_rh.nc").resolve()),
                "cor_rv": str((run_dir / "mpas.cor_rv.nc").resolve()),
            },
            metadata={"members": len(samples), "date": date, "sample_stem": sample_stem},
            status="prepared",
        )
    )
    write_text(
        out / "README.md",
        f"# HDIAG workspace\n\nUNBALANCE workspace: `{unbalance_root}`\nVBAL workspace: `{vbal_root}`\nMembers: {len(samples)}\n"
        f"Samples: `samplesUnbalanced/{sample_stem}_%mem%.nc`\n",
    )
    print("=== HDIAG workspace ===")
    print(f"WORKSPACE={out}")
    print(f"RUN_DIR={run_dir}")
    print(f"MEMBERS={len(samples)}")
    print(f"YAML={run_dir / 'run_hdiag.yaml'}")
    print(f"PBS={run_dir / 'qsub_hdiag.bash'}")
    return out
