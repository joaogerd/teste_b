"""Validation of configured BFLOW products."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

import netCDF4

from ..errors import ArtifactError, ConfigurationError
from .model import BflowPair, compact_time, product_name


def _validation(config: Mapping[str, object]) -> Mapping[str, object]:
    bflow = config.get("bflow")
    if not isinstance(bflow, Mapping) or not isinstance(bflow.get("validation"), Mapping):
        raise ConfigurationError("bflow.validation deve ser um bloco YAML.")
    return bflow["validation"]


def require_vars(path: Path, names: list[str], dimension_checks: Mapping[str, tuple[str, ...]]) -> None:
    """Require configured variables and optional dimensions in a NetCDF product."""
    if not path.is_file():
        raise ArtifactError(f"Produto ausente: {path}")
    with netCDF4.Dataset(path) as dataset:
        for name in names:
            if name not in dataset.variables:
                raise ArtifactError(f"Variável ausente em {path}: {name}")
            expected = dimension_checks.get(name)
            if expected and tuple(dataset.variables[name].dimensions) != expected:
                raise ArtifactError(
                    f"Dimensões inválidas para {name} em {path}: "
                    f"{dataset.variables[name].dimensions}; esperado {expected}"
                )


def validate_products(
    config: Mapping[str, object], workspace: str | Path, pairs: list[BflowPair], stage: str
) -> None:
    """Validate FULL or PTB products using the scientific configuration."""
    if stage not in {"full", "ptb"}:
        raise ValueError(f"stage inválido: {stage}")
    validation = _validation(config)
    required_key = "full_required" if stage == "full" else "ptb_required"
    raw_required = validation.get(required_key, [])
    if not isinstance(raw_required, list) or not all(isinstance(value, str) for value in raw_required):
        raise ConfigurationError(f"bflow.validation.{required_key} deve ser uma lista de nomes.")
    checks: dict[str, tuple[str, ...]] = {}
    raw_checks = validation.get("dimension_checks", [])
    if not isinstance(raw_checks, list):
        raise ConfigurationError("bflow.validation.dimension_checks deve ser uma lista.")
    for item in raw_checks:
        if not isinstance(item, Mapping):
            raise ConfigurationError("Cada dimension_check deve ser um bloco YAML.")
        name = item.get("file")
        dimensions = item.get("dimensions")
        if isinstance(name, str) and isinstance(dimensions, list) and all(isinstance(dim, str) for dim in dimensions):
            checks[name] = tuple(dimensions)

    root = Path(workspace)
    older = product_name(config, "older_full")
    newer = product_name(config, "newer_full")
    perturbation = product_name(config, "perturbation")
    for pair in pairs:
        directory = root / "output" / compact_time(pair.valid_time)
        if stage == "full":
            require_vars(directory / older, raw_required, checks)
            require_vars(directory / newer, raw_required, checks)
        else:
            require_vars(directory / perturbation, raw_required, checks)
