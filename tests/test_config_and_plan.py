from __future__ import annotations

from pathlib import Path

import yaml

from bmatrix.config import deep_merge, load_config
from bmatrix.pipeline import BuildRequest, plan


def test_deep_merge_preserves_nested_contract_settings() -> None:
    merged = deep_merge({"a": {"b": 1, "c": 2}}, {"a": {"b": 3}})
    assert merged == {"a": {"b": 3, "c": 2}}


def test_plan_from_manifest_is_side_effect_free(tmp_path: Path) -> None:
    data = {
        "project": {"work_root": str(tmp_path / "work"), "project_root": str(tmp_path)},
        "mesh": {"name": "x1.test", "grid": str(tmp_path / "mesh.nc"), "nproc": 4},
        "runtime": {"config_dt": 60},
        "bflow": {
            "nmc": {"older_lead_hours": 48, "newer_lead_hours": 24},
            "products": {"template": "template_PTB.nc", "older_full": "FULL_f48.nc", "newer_full": "FULL_f24.nc", "perturbation": "PTB_f48mf24.nc"},
            "regridding": {"resolution_deg": 1.0, "lower_left": [-89.5, -179.5], "upper_right": [89.5, 179.5]},
            "wind_transform": {"outputs": {}},
        },
        "controls": [{"code": "air_temperature", "file": "temperature", "dimensions": "3d"}],
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(data))
    manifest = tmp_path / "manifest.tsv"
    manifest.write_text(
        "valid_time\tf048\tf024\n"
        "2026-06-10_00:00:00\t/a/f048.nc\t/a/f024.nc\n"
    )
    config = load_config(config_path)
    result = plan(config, BuildRequest(manifest=manifest, to_stage="nicas"))
    assert result.stages == ("bflow", "vbal", "hdiag", "nicas")
    assert result.paths.bflow.name.startswith("np4_2026061000")
    assert not result.paths.bflow.exists()
