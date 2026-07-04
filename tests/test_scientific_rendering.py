from __future__ import annotations

from pathlib import Path

import yaml

from bmatrix.dirac_core.config_files import write_dirac_yaml
from bmatrix.hdiag_core.config_files import write_hdiag_yaml
from bmatrix.so_core.config_files import write_so_yaml
from bmatrix.vbal_core.config_files import write_vbal_yaml


def _config() -> dict[str, object]:
    return {
        "mesh": {"name": "x1.test", "nproc": 4},
        "project": {"work_root": "/tmp/work"},
        "install": {"root": "/tmp/install"},
        "bflow": {
            "products": {
                "template": "template.nc",
                "older_full": "older.nc",
                "newer_full": "newer.nc",
                "perturbation": "custom_ptb.nc",
            }
        },
        "controls": [
            {"code": "stream_code", "file": "stream_function", "dimensions": "3d"},
            {"code": "temp_code", "file": "temperature", "dimensions": "3d"},
            {"code": "ps_code", "file": "surface_pressure", "dimensions": "2d"},
        ],
        "vbal": {
            "files_prefix": "mpas",
            "group_variable_order": ["temp_code", "stream_code", "ps_code"],
            "relations": [
                {"balanced_variable": "temp_code", "unbalanced_variable": "stream_code"}
            ],
            "drivers": {},
            "sampling": {},
        },
        "hdiag": {
            "files_prefix": "mpas",
            "drivers": {},
            "sampling": {},
            "variance": {
                "initial_length_scales": [
                    {"variables": ["stream_code", "temp_code"], "value": 1000000.0}
                ]
            },
            "fit": {},
        },
        "nicas": {"files_prefix": "mpas", "drivers": {"multivariate strategy": "univariate"}},
        "dirac": {
            "ndir": 1,
            "index": 1,
            "variable": "temp_code",
            "latitudes": [10.0],
            "longitudes": [20.0],
            "background_variables": ["temperature"],
        },
        "single_observation": {
            "window_hours_before_analysis": 3,
            "window_hours": 6,
            "minimizer": "DRPCG",
            "ninner": 1,
            "gradient_norm_reduction": 0.1,
            "analysis_variables": ["air_temperature"],
            "background_variables": ["temperature"],
            "variants": {"default": ["temperature"]},
            "observations": {
                "temperature": {
                    "name": "SO_T",
                    "simulated_variable": "airTemperature",
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "pressure": 80000.0,
                    "error": 1.0,
                    "value": 280.0,
                    "output_file": "obsout.h5",
                }
            },
        },
    }


def test_renderers_use_declared_product_names_and_control_mapping(tmp_path: Path) -> None:
    config = _config()
    vbal_path = tmp_path / "vbal.yaml"
    hdiag_path = tmp_path / "hdiag.yaml"

    write_vbal_yaml(config, vbal_path, nmembers=4, date="2026-06-10T00:00:00Z")
    write_hdiag_yaml(config, hdiag_path, nmembers=4, date="2026-06-10T00:00:00Z")

    vbal = yaml.safe_load(vbal_path.read_text())
    hdiag = yaml.safe_load(hdiag_path.read_text())
    ensemble = vbal["background error"]["ensemble"]["members from template"]["template"]
    assert ensemble["state variables"] == ["temperature", "stream_function", "surface_pressure"]
    assert ensemble["filename"] == "../samples/custom_ptb_%mem%.nc"
    relation = vbal["background error"]["saber outer blocks"][0]["calibration"]["vertical balance"]["vbal"][0]
    assert relation == {"balanced variable": "temperature", "unbalanced variable": "stream_function"}

    scale = hdiag["background error"]["saber central block"]["calibration"]["variance"]["initial length-scale"][0]
    assert scale["variables"] == ["stream_function", "temperature"]
    hdiag_ensemble = hdiag["background error"]["ensemble"]["members from template"]["template"]
    assert hdiag_ensemble["filename"] == "../samplesUnbalanced/custom_ptb_%mem%.nc"


def test_so_renderer_uses_normalized_vbal_relations(tmp_path: Path) -> None:
    config = _config()
    path = tmp_path / "so.yaml"
    write_so_yaml(
        config,
        path,
        date="2026-06-10T00:00:00Z",
        nicas_dir=tmp_path / "nicas",
        stddev_file=tmp_path / "stddev.nc",
        vbal_dir=tmp_path / "vbal",
    )
    rendered = yaml.safe_load(path.read_text())
    relations = rendered["cost function"]["background error"]["saber outer blocks"][1]["read"]["vertical balance"]["vbal"]
    assert relations == [{"balanced variable": "temperature", "unbalanced variable": "stream_function"}]


def test_dirac_renderer_uses_complete_b_inputs_and_declared_impulse(tmp_path: Path) -> None:
    config = _config()
    path = tmp_path / "dirac.yaml"
    write_dirac_yaml(
        config,
        path,
        date="2026-06-10T00:00:00Z",
        nicas_dir=tmp_path / "nicas",
        stddev_file=tmp_path / "stddev.nc",
        vbal_dir=tmp_path / "vbal",
    )
    rendered = yaml.safe_load(path.read_text())
    output = rendered["output dirac"]
    assert output == {
        "filename": "./mpas.dirac.nc",
        "ndir": 1,
        "ildir": 1,
        "dirvar": "temperature",
        "dirlat": [10.0],
        "dirlon": [20.0],
    }
    assert rendered["background error"]["linear variable change"]["input variables"] == [
        "stream_function",
        "temperature",
        "surface_pressure",
    ]
