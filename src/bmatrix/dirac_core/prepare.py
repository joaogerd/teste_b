"""Prepare DIRAC from explicit NICAS, HDIAG and VBAL artifacts."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Mapping

from ..artifacts import StageManifest, write_manifest
from ..hdiag_core.checks import check as validate_hdiag
from ..hdiag_core.model import hdiag_date
from ..nicas_core.checks import check as validate_nicas
from ..nicas_core.static import link_nicas_support
from ..products import BMatrixProducts
from ..scientific_config import require_background_covers_analysis, section
from ..shell import require_file, write_text
from ..so_core.static import create_jedi_background
from ..vbal_core.validate import validate as validate_vbal
from .config_files import write_dirac_pbs, write_dirac_yaml
from .model import dirac_workspace


def prepare(
    config: Mapping[str, object],
    nicas_workspace: str | Path,
    hdiag_workspace: str | Path,
    vbal_workspace: str | Path,
    workspace: str | Path | None = None,
    clean: bool = False,
) -> Path:
    """Prepare a reproducible complete-B DIRAC diagnostic workspace."""
    nicas_root, hdiag_root, vbal_root = Path(nicas_workspace), Path(hdiag_workspace), Path(vbal_workspace)
    validate_nicas(nicas_root)
    validate_hdiag(hdiag_root)
    validate_vbal(vbal_root)
    products = BMatrixProducts.from_workspaces(
        vbal_workspace=vbal_root,
        hdiag_workspace=hdiag_root,
        nicas_workspace=nicas_root,
    )
    for product in products.required_for_assimilation():
        require_file(product, f"produto B: {product.name}")

    output = Path(workspace) if workspace else dirac_workspace(config, nicas_root)
    if clean and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    hdiag_run = hdiag_root / "HDIAG"
    link_nicas_support(hdiag_run, output)
    templates = sorted(hdiag_run.glob("templateFields.*.nc"))
    if len(templates) != 1:
        raise RuntimeError("Esperado exatamente um templateFields.*.nc no workspace HDIAG para preparar DIRAC.")
    single = section(config, "single_observation")
    background_variables = require_background_covers_analysis(
        section(config, "dirac").get("background_variables", []),
        single.get("analysis_variables", []),
        "dirac",
    )
    create_jedi_background(templates[0], output / "bg.nc", background_variables, "DIRAC")
    date = hdiag_date(hdiag_root)
    write_dirac_yaml(
        config,
        output / "run_dirac.yaml",
        date,
        products.nicas.parent,
        products.stddev,
        products.vbal.parent,
    )
    write_dirac_pbs(config, output)
    write_manifest(
        StageManifest(
            stage="dirac",
            workspace=str(output.resolve()),
            inputs={
                "nicas_workspace": str(nicas_root.resolve()),
                "hdiag_workspace": str(hdiag_root.resolve()),
                "vbal_workspace": str(vbal_root.resolve()),
            },
            outputs={
                "dirac": str((output / "mpas.dirac.nc").resolve()),
                "yaml": str((output / "run_dirac.yaml").resolve()),
            },
            metadata={"date": date},
            status="prepared",
        )
    )
    write_text(output / "README.md", "# DIRAC workspace\n\nMachine-readable provenance: `stage-manifest.json`.\n")
    return output
