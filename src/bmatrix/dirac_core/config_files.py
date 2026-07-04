"""Render the complete-B DIRAC toolbox configuration from YAML settings."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from ..scheduler import bmatrix_job_spec, render_pbs
from ..scientific_config import control_file_names, normalize_control, section
from ..shell import write_text
from ..vbal_core.config_files import render_vbal_relations
from ..vbal_core.model import toolbox_exe


def _number_list(value: object, name: str) -> list[float]:
    """Validate a nonempty numeric YAML sequence."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise ValueError(f"{name} deve ser uma lista numérica não vazia.")
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} deve conter apenas números.") from exc


def _settings(config: Mapping[str, Any]) -> dict[str, object]:
    """Return validated, explicit DIRAC settings from the scientific contract."""
    raw = section(config, "dirac")
    latitudes = _number_list(raw.get("latitudes"), "dirac.latitudes")
    longitudes = _number_list(raw.get("longitudes"), "dirac.longitudes")
    if len(latitudes) != len(longitudes):
        raise ValueError("dirac.latitudes e dirac.longitudes devem ter o mesmo tamanho.")
    index = int(raw.get("index", 1))
    if not 1 <= index <= len(latitudes):
        raise ValueError("dirac.index deve selecionar um ponto configurado.")
    variable = raw.get("variable")
    if not isinstance(variable, str):
        raise ValueError("dirac.variable deve ser uma variável de controle declarada.")
    background_variables = raw.get("background_variables")
    if not isinstance(background_variables, list) or not all(isinstance(item, str) for item in background_variables):
        raise ValueError("dirac.background_variables deve ser uma lista de strings.")
    return {
        "ndir": int(raw.get("ndir", 1)),
        "index": index,
        "variable": normalize_control(config, variable),
        "latitudes": latitudes,
        "longitudes": longitudes,
        "background_variables": list(background_variables),
    }


def write_dirac_yaml(
    config: Mapping[str, Any],
    path: str | Path,
    date: str,
    nicas_dir: Path,
    stddev_file: Path,
    vbal_dir: Path,
) -> None:
    """Render a full-B DIRAC test for the covariance toolbox.

    The file applies the same BUMP_NICAS, StdDev, BUMP_VerticalBalance and
    Control2Analysis composition used by the SO test.  ``output dirac`` is the
    toolbox output block that writes ``mpas.dirac.nc``.
    """
    settings = _settings(config)
    controls = list(control_file_names(config))
    nicas = section(config, "nicas")
    vbal = section(config, "vbal")
    data: dict[str, object] = {
        "geometry": {
            "nml_file": "./namelist.atmosphere_240km",
            "streams_file": "./streams.atmosphere_240km",
            "deallocate non-da fields": True,
        },
        "background": {
            "state variables": settings["background_variables"],
            "filename": "./bg.nc",
            "date": date,
            "transform model to analysis": False,
        },
        "background error": {
            "covariance model": "SABER",
            "saber central block": {
                "saber block name": "BUMP_NICAS",
                "active variables": controls,
                "read": {
                    "io": {
                        "data directory": str(nicas_dir),
                        "files prefix": str(nicas.get("files_prefix", "mpas")),
                    },
                    "drivers": {
                        "multivariate strategy": str(
                            nicas.get("drivers", {}).get("multivariate strategy", "univariate")
                        ),
                        "read local nicas": True,
                    },
                },
            },
            "saber outer blocks": [
                {
                    "saber block name": "StdDev",
                    "read": {
                        "model file": {
                            "filename": str(stddev_file),
                            "date": date,
                            "stream name": "control",
                        }
                    },
                },
                {
                    "saber block name": "BUMP_VerticalBalance",
                    "read": {
                        "io": {
                            "data directory": str(vbal_dir),
                            "files prefix": str(vbal.get("files_prefix", "mpas")),
                        },
                        "drivers": {"read local sampling": True, "read vertical balance": True},
                        "vertical balance": {"vbal": render_vbal_relations(config)},
                    },
                },
            ],
            "linear variable change": {
                "linear variable change name": "Control2Analysis",
                "input variables": controls,
                "output variables": settings["background_variables"],
            },
        },
        "output dirac": {
            "filename": "./mpas.dirac.nc",
            "ndir": settings["ndir"],
            "ildir": settings["index"],
            "dirvar": settings["variable"],
            "dirlat": settings["latitudes"],
            "dirlon": settings["longitudes"],
        },
    }
    write_text(Path(path), yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def write_dirac_pbs(config: Mapping[str, Any], run_dir: str | Path) -> None:
    """Write the standard PBS script for the full-B DIRAC toolbox diagnostic."""
    directory = Path(run_dir)
    ranks = int(config["mesh"].get("nproc", config.get("pbs", {}).get("nproc", 1)))
    spec = bmatrix_job_spec(
        config,
        name="DiracTest",
        run_dir=directory,
        command=("mpiexec", "-n", str(ranks), str(toolbox_exe(config)), "./run_dirac.yaml", "./run_dirac.runlog"),
    )
    write_text(directory / "qsub_dirac.bash", render_pbs(spec))
