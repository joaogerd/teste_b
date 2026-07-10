from __future__ import annotations

import pytest

from bmatrix.hdiag_core.config_files import validate_sampling_extent
from bmatrix.hdiag_core.model import hdiag_date


def test_hdiag_sampling_extent_accepts_tutorial_width() -> None:
    validate_sampling_extent(
        {
            "sampling": {
                "distance classes": 10,
                "distance class width": 1000000.0,
            }
        }
    )


def test_hdiag_sampling_extent_rejects_bins_beyond_bump_universe() -> None:
    with pytest.raises(ValueError, match="excede universe length-scale"):
        validate_sampling_extent(
            {
                "sampling": {
                    "distance classes": 10,
                    "distance class width": 3000000.0,
                }
            }
        )


def test_hdiag_date_accepts_rendered_yaml_without_anchor(tmp_path) -> None:
    run_dir = tmp_path / "HDIAG"
    run_dir.mkdir()
    (run_dir / "run_hdiag.yaml").write_text("background:\n  date: '2026-06-22T00:00:00Z'\n")

    assert hdiag_date(tmp_path) == "2026-06-22T00:00:00Z"


def test_hdiag_date_accepts_tutorial_anchor(tmp_path) -> None:
    run_dir = tmp_path / "HDIAG"
    run_dir.mkdir()
    (run_dir / "run_hdiag.yaml").write_text("background:\n  date: &date '2018-04-15T00:00:00Z'\n")

    assert hdiag_date(tmp_path) == "2018-04-15T00:00:00Z"
