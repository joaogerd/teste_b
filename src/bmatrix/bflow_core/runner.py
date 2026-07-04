"""One coherent BFLOW execution service."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Mapping

from ..artifacts import StageManifest, write_manifest
from .manifest import read_manifest
from .model import BflowPair, compact_time, product_name
from .weights import ensure_esmf_weights, generate_esmf_weights


def clean_outputs(workspace: str | Path) -> None:
    """Remove only reproducible BFLOW products, preserving input provenance."""
    output = Path(workspace) / "output"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)


def load_workspace_pairs(workspace: str | Path) -> list[BflowPair]:
    """Load the stable TSV input contract for a prepared BFLOW workspace."""
    return read_manifest(Path(workspace) / "manifest.tsv")


def list_ptb_samples(config: Mapping[str, object], workspace: str | Path, pairs: list[BflowPair]) -> list[Path]:
    """Return the calibrated sample path for each valid time."""
    root = Path(workspace)
    product = product_name(config, "perturbation")
    return [root / "output" / compact_time(pair.valid_time) / product for pair in pairs]


def run_bflow_pipeline(
    config: Mapping[str, object],
    workspace: str | Path,
    pairs: list[BflowPair] | None = None,
    clean_output: bool = False,
    skip_weights: bool = False,
) -> list[Path]:
    """Generate all BFLOW products from NMC forecast pairs.

    This function is deliberately local and deterministic: the only external
    scientific dependencies are ESMPy and windspharm, both invoked by Python.
    """
    root = Path(workspace).resolve()
    active_pairs = pairs or load_workspace_pairs(root)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "output").mkdir(parents=True, exist_ok=True)
    if clean_output:
        clean_outputs(root)
    if skip_weights:
        ensure_esmf_weights(config, root)
    else:
        generate_esmf_weights(config, root)

    # Import NetCDF- and windspharm-dependent steps only for a real run.
    from .diff import diff_pairs
    from .psichi import convert_uv_to_psichi
    from .template import generate_template_ptb
    from .validate import validate_products
    from .variables import add_variables_for_pairs

    generate_template_ptb(config, active_pairs[0].f048, root)
    convert_uv_to_psichi(config, root, active_pairs)
    validate_products(config, root, active_pairs, stage="full")
    add_variables_for_pairs(config, root, active_pairs)
    diff_pairs(config, root, active_pairs)
    validate_products(config, root, active_pairs, stage="ptb")

    samples = list_ptb_samples(config, root, active_pairs)
    write_manifest(
        StageManifest(
            stage="bflow",
            workspace=str(root),
            inputs={"pair_manifest": str(root / "manifest.tsv")},
            outputs={
                "template": str(root / product_name(config, "template")),
                "samples": str(root / "output"),
                "weights": str((root / "ESMF_weights")),
            },
            metadata={"members": len(samples), "sample_files": [str(path) for path in samples]},
            status="completed",
        )
    )
    return samples
