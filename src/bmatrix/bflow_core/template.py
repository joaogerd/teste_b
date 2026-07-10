"""Creation of the minimal NetCDF template used by the wind transform."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

import netCDF4

from ..errors import ArtifactError, ConfigurationError
from .netcdf_utils import CDF5_FORMAT, copy_attrs


def _wind_outputs(config: Mapping[str, object]) -> Mapping[str, object]:
    bflow = config.get("bflow")
    if not isinstance(bflow, Mapping) or not isinstance(bflow.get("wind_transform"), Mapping):
        raise ConfigurationError("bflow.wind_transform deve ser um bloco YAML.")
    transform = bflow["wind_transform"]
    outputs = transform.get("outputs")
    if not isinstance(outputs, Mapping):
        raise ConfigurationError("bflow.wind_transform.outputs deve ser um bloco YAML.")
    return outputs


def generate_template_ptb(config: Mapping[str, object], first_ref: str | Path, workspace: str | Path) -> Path:
    """Create a CDF5 template containing only configured psi/chi output variables."""
    source = Path(first_ref)
    root = Path(workspace)
    products = config["bflow"]["products"]  # type: ignore[index]
    if not isinstance(products, Mapping):
        raise ConfigurationError("bflow.products deve ser um bloco YAML.")
    output = root / str(products["template"])
    if not source.is_file():
        raise ArtifactError(f"Arquivo de referência ausente: {source}")
    if output.exists():
        output.unlink()

    outputs = _wind_outputs(config)
    with netCDF4.Dataset(source) as src, netCDF4.Dataset(output, "w", format=CDF5_FORMAT) as dst:
        template_name = str(config["bflow"]["wind_transform"].get("template_file_variable", "theta"))  # type: ignore[index]
        if template_name not in src.variables:
            raise ArtifactError(f"Variável template ausente: {template_name} em {source}")
        template = src.variables[template_name]
        for dim_name in template.dimensions:
            dim = src.dimensions[dim_name]
            dst.createDimension(dim_name, None if dim.isunlimited() else len(dim))
        copy_attrs(src, dst)
        for output_name, metadata in outputs.items():
            if not isinstance(metadata, Mapping):
                raise ConfigurationError(f"bflow.wind_transform.outputs.{output_name} inválido.")
            file_name = str(metadata.get("file", output_name))
            kwargs: dict[str, object] = {}
            fill_value = getattr(template, "_FillValue", None)
            if fill_value is not None:
                kwargs["fill_value"] = fill_value
            variable = dst.createVariable(file_name, template.dtype, template.dimensions, **kwargs)
            variable[:] = template[:] * 0.0
            variable.setncattr("long_name", str(metadata.get("long_name", output_name)))
            variable.setncattr("units", str(metadata.get("units", "m^2 s^(-2)")))
    return output
