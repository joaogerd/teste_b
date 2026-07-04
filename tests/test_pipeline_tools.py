from pathlib import Path

from bmatrix.bflow_core.weights import weight_paths
from bmatrix.products import BMatrixProducts


def test_bflow_weight_paths_are_defined_by_one_esmpy_contract(tmp_path: Path) -> None:
    config = {
        "mesh": {"name": "x1.test", "grid": str(tmp_path / "mesh.nc")},
        "bflow": {
            "regridding": {
                "weights_directory": "weights/{mesh_name}",
                "resolution_deg": 1.0,
                "latlon_grid_id": "latlon_1p0",
                "lower_left": [-89.5, -179.5],
                "upper_right": [89.5, 179.5],
            }
        },
    }
    mpas_to_latlon, latlon_to_mpas = weight_paths(config, tmp_path)
    assert mpas_to_latlon == tmp_path / "weights/x1.test/MPAS_x1.test_to_latlon_1p0_bilinear.nc"
    assert latlon_to_mpas == tmp_path / "weights/x1.test/latlon_1p0_to_MPAS_x1.test_bilinear.nc"


def test_product_layout_contains_required_saber_products(tmp_path: Path) -> None:
    products = BMatrixProducts.from_workspaces(
        vbal_workspace=tmp_path / "vbal", hdiag_workspace=tmp_path / "hdiag", nicas_workspace=tmp_path / "nicas"
    )
    assert {path.name for path in products.required_for_assimilation()} == {
        "mpas_vbal.nc", "mpas_sampling.nc", "mpas.stddev.nc", "mpas_nicas.nc"
    }
