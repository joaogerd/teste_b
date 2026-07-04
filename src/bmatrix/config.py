"""Configuration loading for the MPAS-JEDI static B-matrix workflow.

The workflow uses two declarative documents:

* a *platform* YAML containing paths, scheduler, MPI and runtime details;
* a *scientific contract* YAML containing controls and calibration settings.

The platform document may point to the contract through
``bmatrix.configuration``.  They are deep-merged so that nested infrastructure
settings do not erase scientific defaults accidentally.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any
import os

import yaml

from .errors import ConfigurationError

Config = dict[str, Any]


def _load_yaml(path: Path) -> Config:
    """Load one YAML mapping and report configuration errors explicitly."""
    if not path.is_file():
        raise ConfigurationError(f"Configuração não encontrada: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"YAML inválido em {path}: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ConfigurationError(f"A raiz da configuração deve ser um mapa YAML: {path}")
    return dict(raw)


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> Config:
    """Merge mappings recursively without merging list values implicitly.

    Lists are atomic: an override must intentionally replace a list of controls,
    variables or driver settings.  This prevents accidental concatenation of
    scientifically meaningful sequences.
    """
    result: Config = deepcopy(dict(base))
    for key, value in override.items():
        old = result.get(key)
        if isinstance(old, Mapping) and isinstance(value, Mapping):
            result[key] = deep_merge(old, value)
        else:
            result[key] = deepcopy(value)
    return result


def expand_env(value: Any) -> Any:
    """Expand environment variables recursively in a decoded YAML value."""
    if isinstance(value, Mapping):
        return {str(key): expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [expand_env(item) for item in value]
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value


def _contract_path(platform_path: Path, platform: Mapping[str, Any]) -> Path | None:
    bmatrix = platform.get("bmatrix")
    if bmatrix is None:
        return None
    if not isinstance(bmatrix, Mapping):
        raise ConfigurationError("bmatrix deve ser um bloco YAML.")
    specification = bmatrix.get("configuration")
    if specification is None:
        return None
    if not isinstance(specification, str) or not specification.strip():
        raise ConfigurationError("bmatrix.configuration deve ser um caminho YAML não vazio.")
    candidate = Path(os.path.expandvars(specification)).expanduser()
    return candidate if candidate.is_absolute() else (platform_path.parent / candidate).resolve()


def load_config(path: str | Path) -> Config:
    """Load the platform configuration and its optional B-matrix contract.

    Parameters
    ----------
    path
        Platform YAML.  Its optional ``bmatrix.configuration`` field identifies
        the scientific contract YAML.

    Returns
    -------
    dict[str, object]
        Deep-merged configuration.  ``bmatrix_contract`` and
        ``bmatrix_contract_path`` retain the unmerged scientific source for
        provenance.
    """
    platform_path = Path(path).expanduser().resolve()
    platform = expand_env(_load_yaml(platform_path))
    contract_path = _contract_path(platform_path, platform)
    if contract_path is None:
        merged = dict(platform)
    else:
        contract = expand_env(_load_yaml(contract_path))
        merged = deep_merge(contract, platform)
        merged["bmatrix_contract"] = contract
        merged["bmatrix_contract_path"] = str(contract_path)
    validate_config_shape(merged)
    return merged


def validate_config_shape(config: Mapping[str, Any]) -> None:
    """Perform lightweight validation shared by all workflow stages.

    Detailed stage validation is intentionally deferred until a stage is
    selected.  A BFLOW-only run therefore does not need a configured SABER
    executable, while a VBAL run does.
    """
    required_maps = ("project", "mesh", "runtime", "bflow")
    missing = [name for name in required_maps if not isinstance(config.get(name), Mapping)]
    if missing:
        raise ConfigurationError("Blocos de configuração obrigatórios ausentes: " + ", ".join(missing))
    mesh = config["mesh"]
    for key in ("name", "grid"):
        if not isinstance(mesh.get(key), str) or not mesh[key]:
            raise ConfigurationError(f"mesh.{key} é obrigatório.")
    bflow = config["bflow"]
    for key in ("nmc", "products", "regridding", "wind_transform"):
        if not isinstance(bflow.get(key), Mapping):
            raise ConfigurationError(f"bflow.{key} deve ser um bloco YAML.")


def safe_time(init_time: str) -> str:
    """Return an MPAS-safe time label with dots instead of colons."""
    return init_time.replace(":", ".")


def ymdh(init_time: str) -> str:
    """Return ``YYYYMMDDHH`` from a standard MPAS timestamp."""
    return init_time[0:4] + init_time[5:7] + init_time[8:10] + init_time[11:13]


def date_part(init_time: str) -> str:
    """Return ``YYYYMMDD`` from a standard MPAS timestamp."""
    return init_time[0:4] + init_time[5:7] + init_time[8:10]


def cycle_part(init_time: str) -> str:
    """Return the UTC cycle hour from a standard MPAS timestamp."""
    return init_time[11:13]
