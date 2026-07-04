"""Render HDIAG configuration from the declared B-matrix contract."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from ..scheduler import bmatrix_job_spec, render_pbs
from ..scientific_config import bflow_sample_stem, control_file_names, normalize_control, section
from ..shell import write_text
from ..vbal_core.model import toolbox_exe


def _initial_length_scales(config: Mapping[str, Any], hdiag: Mapping[str, Any], variables: list[str]) -> list[dict[str, object]]:
    """Translate configured length-scale controls into MPAS NetCDF variable names."""
    variance = hdiag.get("variance", {})
    if not isinstance(variance, Mapping):
        raise ValueError("hdiag.variance deve ser um bloco YAML.")
    configured = variance.get("initial_length_scales", [])
    if not isinstance(configured, list):
        raise ValueError("hdiag.variance.initial_length_scales deve ser uma lista.")
    result: list[dict[str, object]] = []
    for item in configured:
        if not isinstance(item, Mapping):
            raise ValueError("Cada initial_length_scales deve ser um bloco YAML.")
        raw_variables = item.get("variables", variables)
        if not isinstance(raw_variables, list):
            raise ValueError("initial_length_scales.variables deve ser uma lista.")
        result.append(
            {
                "variables": [normalize_control(config, str(value)) for value in raw_variables],
                "value": float(item["value"]),
            }
        )
    return result


def write_hdiag_yaml(config: Mapping[str, Any], path: str | Path, nmembers: int, date: str, sample_stem: str | None = None) -> None:
    """Render HDIAG calibration YAML using configured drivers and sampling rules."""
    hdiag = section(config, "hdiag")
    variables = list(control_file_names(config))
    stem = sample_stem or bflow_sample_stem(config)
    variance = hdiag.get("variance", {})
    if not isinstance(variance, Mapping):
        raise ValueError("hdiag.variance deve ser um bloco YAML.")
    data: dict[str, object] = {
        "geometry": {
            "nml_file": "./namelist.atmosphere_240km",
            "streams_file": "./streams.atmosphere_240km",
            "bump vunit": str(hdiag.get("bump_vunit", "avgheight")),
        },
        "background": {
            "state variables": variables,
            "filename": "./bg.nc",
            "date": date,
            "stream name": "control",
            "transform model to analysis": False,
        },
        "background error": {
            "covariance model": "SABER",
            "iterative ensemble loading": bool(hdiag.get("iterative_ensemble_loading", True)),
            "ensemble": {
                "members from template": {
                    "template": {
                        "state variables": variables,
                        "date": date,
                        "stream name": "control",
                        "transform model to analysis": False,
                        "filename": f"../samplesUnbalanced/{stem}_%mem%.nc",
                    },
                    "pattern": "%mem%",
                    "nmembers": nmembers,
                    "zero padding": 3,
                }
            },
            "saber central block": {
                "saber block name": "BUMP_NICAS",
                "calibration": {
                    "io": {"files prefix": str(hdiag.get("files_prefix", "mpas"))},
                    "drivers": dict(hdiag.get("drivers", {})),
                    "sampling": dict(hdiag.get("sampling", {})),
                    "variance": {
                        "objective filtering": bool(variance.get("objective_filtering", True)),
                        "filtering iterations": int(variance.get("filtering_iterations", 1)),
                        "initial length-scale": _initial_length_scales(config, hdiag, variables),
                    },
                    "fit": dict(hdiag.get("fit", {})),
                    "output model files": [
                        {"parameter": "stddev", "file": {"filename": "./mpas.stddev.nc", "date": date, "stream name": "control"}},
                        {"parameter": "cor_rh", "file": {"filename": "./mpas.cor_rh.nc", "date": date, "stream name": "control"}},
                        {"parameter": "cor_rv", "file": {"filename": "./mpas.cor_rv.nc", "date": date, "stream name": "control"}},
                    ],
                },
            },
        },
    }
    write_text(Path(path), yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def write_hdiag_pbs(config: Mapping[str, Any], run_dir: str | Path) -> None:
    """Write the standardized PBS job for HDIAG."""
    directory = Path(run_dir)
    ranks = int(config["mesh"].get("nproc", config.get("pbs", {}).get("nproc", 1)))
    spec = bmatrix_job_spec(
        config,
        name="mpasjediBTrainingHDIAG",
        run_dir=directory,
        command=("mpiexec", "-n", str(ranks), str(toolbox_exe(config)), "./run_hdiag.yaml", "./run_hdiag.runlog"),
    )
    write_text(directory / "qsub_hdiag.bash", render_pbs(spec))
