from __future__ import annotations

from pathlib import Path

import netCDF4
import numpy as np

from bmatrix.plots_core.runner import generate_plots, plots_workspace_from_bflow, validate_plots
from bmatrix.products import BMatrixProducts


def _write_product(path: Path, variable: str = "temperature") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with netCDF4.Dataset(path, "w", format="NETCDF4") as dataset:
        dataset.createDimension("Time", 1)
        dataset.createDimension("nCells", 3)
        dataset.createDimension("nVertLevels", 2)
        lon = dataset.createVariable("lonCell", "f8", ("nCells",))
        lat = dataset.createVariable("latCell", "f8", ("nCells",))
        lon[:] = np.array([0.0, 0.1, 0.2])
        lat[:] = np.array([-0.1, 0.0, 0.1])
        values = dataset.createVariable(variable, "f4", ("Time", "nCells", "nVertLevels"))
        values[:] = np.arange(6, dtype="f4").reshape(1, 3, 2)


def test_plots_workspace_from_bflow_uses_run_id() -> None:
    workspace = plots_workspace_from_bflow(
        {"project": {"work_root": "/work/root"}},
        "/work/root/bmatrix/bflow_preprocessing/np128_2026062200_2026062500",
    )
    assert workspace == Path("/work/root/bmatrix/plots/np128_2026062200_2026062500")


def test_generate_plots_writes_summary_readme_and_figures(tmp_path: Path) -> None:
    product_paths = {
        "vbal": tmp_path / "vbal.nc",
        "sampling": tmp_path / "sampling.nc",
        "stddev": tmp_path / "stddev.nc",
        "cor_rh": tmp_path / "cor_rh.nc",
        "cor_rv": tmp_path / "cor_rv.nc",
        "nicas": tmp_path / "nicas.nc",
        "nicas_norm": tmp_path / "nicas_norm.nc",
        "dirac_nicas": tmp_path / "dirac_nicas.nc",
        "dirac": tmp_path / "dirac.nc",
    }
    for path in product_paths.values():
        _write_product(path)

    products = BMatrixProducts(**product_paths)
    out = generate_plots(
        products,
        tmp_path / "plots",
        clean=True,
        variables=("temperature",),
        level=1,
        dpi=50,
    )

    assert out["summary"].is_file()
    assert out["readme"].is_file()
    assert list((tmp_path / "plots").glob("**/*.png"))
    assert "temperature" in out["summary"].read_text()
    validate_plots(tmp_path / "plots")
