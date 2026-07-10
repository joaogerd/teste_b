from __future__ import annotations

import pytest

from bmatrix.bflow_core.diff import diff_file
from bmatrix.bflow_core.netcdf_utils import CDF5_FORMAT
from bmatrix.bflow_core.template import generate_template_ptb
from bmatrix.vbal_core.model import Sample
from bmatrix.vbal_core.static import stage_samples


def _write_source(path):
    netcdf4 = pytest.importorskip("netCDF4")
    with netcdf4.Dataset(path, "w") as dataset:
        dataset.createDimension("Time", 1)
        dataset.createDimension("nCells", 2)
        dataset.createDimension("nVertLevels", 1)
        theta = dataset.createVariable("theta", "f4", ("Time", "nCells", "nVertLevels"))
        theta[:] = 280.0


def test_template_ptb_is_written_as_cdf5(tmp_path):
    netcdf4 = pytest.importorskip("netCDF4")
    source = tmp_path / "reference.nc"
    _write_source(source)
    config = {
        "bflow": {
            "products": {"template": "template_PTB.nc"},
            "wind_transform": {
                "template_file_variable": "theta",
                "outputs": {"stream_function": {"file": "stream_function"}},
            },
        }
    }

    output = generate_template_ptb(config, source, tmp_path)

    with netcdf4.Dataset(output) as dataset:
        assert dataset.data_model == CDF5_FORMAT


def test_ptb_difference_is_written_as_cdf5(tmp_path):
    netcdf4 = pytest.importorskip("netCDF4")
    older = tmp_path / "older.nc"
    newer = tmp_path / "newer.nc"
    output = tmp_path / "PTB.nc"
    _write_source(older)
    _write_source(newer)

    diff_file(older, newer, output, "2026-06-22_00:00:00")

    with netcdf4.Dataset(output) as dataset:
        assert dataset.data_model == CDF5_FORMAT


def test_vbal_stages_cdf5_samples_as_links(tmp_path):
    source = tmp_path / "PTB_f48mf24.nc"
    source.touch()
    config = {"bflow": {"products": {"perturbation": "PTB_f48mf24.nc"}}}
    sample = Sample(
        valid_time="2026-06-22_00:00:00",
        ptb=source,
        full_f24=tmp_path / "FULL_f24.nc",
        template_fields=tmp_path / "templateFields.nc",
    )

    stem = stage_samples(config, tmp_path / "vbal", [sample])
    staged = tmp_path / "vbal" / "samples" / "PTB_f48mf24_001.nc"

    assert stem == "PTB_f48mf24"
    assert staged.is_symlink()
    assert staged.resolve() == source.resolve()
