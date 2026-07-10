"""Config-driven derived control-variable production for BFLOW."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

import netCDF4
import numpy as np

from ..errors import ArtifactError, ConfigurationError
from .model import BflowPair, compact_time, product_name
from .netcdf_utils import ensure_dims, upsert_var


def _bflow(config: Mapping[str, object]) -> Mapping[str, object]:
    value = config.get("bflow")
    if not isinstance(value, Mapping):
        raise ConfigurationError("bflow deve ser um bloco YAML.")
    return value


def _control_file_names(config: Mapping[str, object]) -> dict[str, str]:
    controls = config.get("controls", [])
    if not isinstance(controls, list):
        raise ConfigurationError("controls deve ser uma lista.")
    result: dict[str, str] = {}
    for item in controls:
        if not isinstance(item, Mapping):
            raise ConfigurationError("Cada control deve ser um bloco YAML.")
        code, file_name = item.get("code"), item.get("file")
        if isinstance(code, str) and isinstance(file_name, str):
            result[code] = file_name
    return result


def _output_file(spec: Mapping[str, object], control_files: Mapping[str, str]) -> str:
    value = spec.get("output_file") or spec.get("output_control")
    if not isinstance(value, str) or not value:
        raise ConfigurationError("derived_variables requer output_file ou output_control.")
    return control_files.get(value, value)


def _apply_derived(
    source: netCDF4.Dataset,
    destination: netCDF4.Dataset,
    spec: Mapping[str, object],
    control_files: Mapping[str, str],
) -> None:
    operation = str(spec.get("operation", "")).strip()
    output_name = _output_file(spec, control_files)
    attributes = spec.get("attributes", {})
    if not isinstance(attributes, Mapping):
        raise ConfigurationError(f"Atributos de {output_name} devem ser um mapa.")

    if operation == "sum":
        inputs = spec.get("inputs")
        if not isinstance(inputs, list) or len(inputs) < 2 or not all(isinstance(name, str) for name in inputs):
            raise ConfigurationError(f"derived_variables {output_name}: sum requer inputs com ao menos dois nomes.")
        missing = [name for name in inputs if name not in source.variables]
        if missing:
            raise ArtifactError(f"Variáveis ausentes para {output_name}: {', '.join(missing)}")
        template_name = str(spec.get("template_file", inputs[0]))
        template = source.variables[template_name]
        values = sum(np.asarray(source.variables[name][:]) for name in inputs)
    elif operation == "potential_temperature_to_temperature":
        theta_name = str(spec.get("theta_file", "theta"))
        pressure_name = str(spec.get("pressure_file", "pressure"))
        if theta_name not in source.variables or pressure_name not in destination.variables:
            raise ArtifactError(f"Variáveis ausentes para {output_name}: {theta_name}/{pressure_name}")
        template = source.variables[str(spec.get("template_file", theta_name))]
        pressure = np.asarray(destination.variables[pressure_name][:])
        reference = float(spec.get("reference_pressure_pa", 100000.0))
        exponent = float(spec.get("exponent", 2.0 / 7.0))
        values = np.asarray(source.variables[theta_name][:]) * ((pressure / reference) ** exponent)
    elif operation == "mixing_ratio_to_specific_humidity":
        mixing_name = str(spec.get("mixing_ratio_file", "qv"))
        if mixing_name not in source.variables:
            raise ArtifactError(f"Variável ausente para {output_name}: {mixing_name}")
        template = source.variables[str(spec.get("template_file", mixing_name))]
        mixing_ratio = np.asarray(source.variables[mixing_name][:])
        values = mixing_ratio / (1.0 + mixing_ratio)
    else:
        raise ConfigurationError(f"Operação BFLOW não suportada: {operation!r}")

    ensure_dims(source, destination, template)
    variable = upsert_var(destination, template, output_name, values.astype(template.dtype, copy=False))
    for key, value in attributes.items():
        variable.setncattr(str(key), value)


def add_variables(config: Mapping[str, object], input_path: str | Path, full_path: str | Path) -> None:
    """Copy configured fields and calculate configured derived products."""
    source_path, destination_path = Path(input_path), Path(full_path)
    if not destination_path.is_file():
        raise ArtifactError(f"FULL file não existe; rode primeiro uv_to_psichi: {destination_path}")
    bflow = _bflow(config)
    copy_variables = bflow.get("copy_variables", [])
    derived_variables = bflow.get("derived_variables", [])
    if not isinstance(copy_variables, list) or not all(isinstance(name, str) for name in copy_variables):
        raise ConfigurationError("bflow.copy_variables deve ser uma lista de nomes.")
    if not isinstance(derived_variables, list):
        raise ConfigurationError("bflow.derived_variables deve ser uma lista.")
    controls = _control_file_names(config)

    with netCDF4.Dataset(source_path) as source, netCDF4.Dataset(destination_path, "a") as destination:
        for name in copy_variables:
            if name not in source.variables:
                raise ArtifactError(f"Variável configurada ausente em {source_path}: {name}")
            variable = source.variables[name]
            ensure_dims(source, destination, variable)
            upsert_var(destination, variable, name)
        for raw in derived_variables:
            if not isinstance(raw, Mapping):
                raise ConfigurationError("Cada derived_variable deve ser um bloco YAML.")
            _apply_derived(source, destination, raw, controls)


def add_variables_for_pairs(config: Mapping[str, object], workspace: str | Path, pairs: list[BflowPair]) -> None:
    """Apply the configured derived-field rules to both forecasts in each pair."""
    root = Path(workspace)
    older_name = product_name(config, "older_full")
    newer_name = product_name(config, "newer_full")
    for pair in pairs:
        directory = root / "output" / compact_time(pair.valid_time)
        add_variables(config, pair.f048, directory / older_name)
        add_variables(config, pair.f024, directory / newer_name)
