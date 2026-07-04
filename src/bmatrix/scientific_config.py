"""Validated accessors for the MPAS-JEDI/SABER scientific contract."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .errors import ConfigurationError


def section(config: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    """Return a required mapping section from a loaded configuration.

    Parameters
    ----------
    config
        Fully merged workflow configuration.
    name
        Required top-level YAML block.

    Returns
    -------
    Mapping[str, Any]
        The validated section.
    """
    value = config.get(name)
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"{name} deve ser um bloco YAML.")
    return value


def controls(config: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    """Return declared B-matrix controls in configured order."""
    raw = config.get("controls")
    if not isinstance(raw, list) or not raw:
        raise ConfigurationError("controls deve ser uma lista não vazia.")
    parsed = tuple(item for item in raw if isinstance(item, Mapping))
    if len(parsed) != len(raw):
        raise ConfigurationError("Cada item de controls deve ser um bloco YAML.")
    for item in parsed:
        if not isinstance(item.get("code"), str) or not isinstance(item.get("file"), str):
            raise ConfigurationError("Cada control requer code e file.")
    return parsed


def control_file_names(config: Mapping[str, Any]) -> tuple[str, ...]:
    """Return physical NetCDF control variable names."""
    return tuple(str(item["file"]) for item in controls(config))


def control_code_to_file(config: Mapping[str, Any]) -> dict[str, str]:
    """Map JEDI control codes to physical NetCDF names."""
    return {str(item["code"]): str(item["file"]) for item in controls(config)}


def normalize_control(config: Mapping[str, Any], value: str) -> str:
    """Resolve a canonical code or physical NetCDF name to its file name."""
    mapping = control_code_to_file(config)
    if value in mapping:
        return mapping[value]
    if value in mapping.values():
        return value
    raise ConfigurationError(f"Variável de controle não declarada: {value}")


def ordered_control_file_names(
    config: Mapping[str, Any], values: object | None = None
) -> tuple[str, ...]:
    """Resolve an optional configured control ordering.

    Parameters
    ----------
    config
        Fully merged workflow configuration.
    values
        ``None`` to keep the global ``controls`` order, or a YAML list containing
        declared control codes and/or physical NetCDF variable names.

    Returns
    -------
    tuple[str, ...]
        Validated physical variable names, without duplicates.
    """
    if values is None:
        return control_file_names(config)
    raw = list_of_strings(values, "ordem de variáveis")
    result = tuple(normalize_control(config, item) for item in raw)
    if len(set(result)) != len(result):
        raise ConfigurationError("A ordem de variáveis contém controles repetidos.")
    return result


def bflow_product(config: Mapping[str, Any], name: str) -> str:
    """Return a configured BFLOW product filename.

    Parameters
    ----------
    config
        Fully merged workflow configuration.
    name
        One of ``template``, ``older_full``, ``newer_full`` or ``perturbation``.
    """
    bflow = section(config, "bflow")
    products = bflow.get("products")
    if not isinstance(products, Mapping):
        raise ConfigurationError("bflow.products deve ser um bloco YAML.")
    value = products.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"bflow.products.{name} deve ser um nome de arquivo.")
    filename = Path(value)
    if filename.name != value or filename.suffix != ".nc":
        raise ConfigurationError(
            f"bflow.products.{name} deve ser um nome simples terminado em .nc: {value!r}"
        )
    return value


def bflow_sample_stem(config: Mapping[str, Any]) -> str:
    """Return the canonical staged-sample stem derived from BFLOW perturbations."""
    return Path(bflow_product(config, "perturbation")).stem


def list_of_strings(value: object, name: str) -> tuple[str, ...]:
    """Validate a string list from a YAML contract."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ConfigurationError(f"{name} deve ser uma lista de strings.")
    result = tuple(str(item) for item in value)
    if not all(item for item in result):
        raise ConfigurationError(f"{name} contém item vazio.")
    return result
