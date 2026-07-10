"""Plotting and summary helpers for completed MPAS-JEDI/SABER B-matrix products."""
from __future__ import annotations

import csv
from dataclasses import asdict
import math
from pathlib import Path
import shutil
from typing import Iterable, Mapping, Sequence

from ..products import BMatrixProducts

DEFAULT_PLOT_VARIABLES: tuple[str, ...] = (
    "temperature",
    "surface_pressure",
    "stream_function",
    "velocity_potential",
    "spechum",
    "air_temperature",
    "air_pressure_at_surface",
    "water_vapor_mixing_ratio_wrt_moist_air",
)

SUMMARY_COLUMNS: tuple[str, ...] = (
    "product",
    "path",
    "variable",
    "shape",
    "min",
    "max",
    "mean",
    "rms",
    "max_abs",
    "nonzero_count",
)


def plots_workspace_from_bflow(config: Mapping[str, object], bflow_workspace: str | Path) -> Path:
    """Return the deterministic plots workspace for a BFLOW workspace."""
    project = config.get("project", {})
    if not isinstance(project, Mapping):
        raise ValueError("Configuração inválida: seção project ausente.")
    work_root = Path(str(project.get("work_root", ".")))
    return work_root / "bmatrix" / "plots" / Path(bflow_workspace).name


def generate_plots(
    products: BMatrixProducts,
    workspace: str | Path,
    *,
    clean: bool = False,
    level: int = 30,
    dpi: int = 150,
    variables: Sequence[str] | None = None,
) -> dict[str, Path]:
    """Generate CSV summaries and simple PNG diagnostics for final B-matrix products.

    The plots are intentionally lightweight: they use ``lonCell``/``latCell`` when
    present and fall back to plotting values against the cell/index coordinate.
    This keeps the stage usable on JACI without requiring Cartopy.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import netCDF4
        import numpy as np
    except ImportError as exc:  # pragma: no cover - depends on runtime environment
        raise RuntimeError("A etapa plots requer netCDF4, numpy e matplotlib.") from exc

    root = Path(workspace)
    if clean and root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    selected = tuple(variables or DEFAULT_PLOT_VARIABLES)
    product_map = _product_map(products)
    summary_rows: list[dict[str, object]] = []
    figures: list[Path] = []

    for product_name, path in product_map.items():
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Produto obrigatório ausente para plots: {path}")

        with netCDF4.Dataset(path) as dataset:
            summary_rows.extend(_summarize_dataset(product_name, path, dataset, np=np))
            figures.extend(
                _plot_dataset(
                    product_name,
                    path,
                    dataset,
                    root,
                    selected,
                    level=level,
                    dpi=dpi,
                    plt=plt,
                    np=np,
                )
            )

    summary_csv = root / "summary.csv"
    _write_summary_csv(summary_csv, summary_rows)
    readme = root / "README.md"
    _write_readme(readme, products, summary_csv, figures, level=level, dpi=dpi)

    print("=== PLOTS validation ===")
    print(f"WORKSPACE={root}")
    print(f"SUMMARY={summary_csv}")
    print(f"FIGURES={len(figures)}")
    print("SUCCESS: PLOTS gerados.")
    return {"workspace": root, "summary": summary_csv, "readme": readme}


def validate_plots(workspace: str | Path) -> bool:
    """Validate a completed plots workspace."""
    root = Path(workspace)
    summary = root / "summary.csv"
    readme = root / "README.md"
    if not summary.is_file():
        raise FileNotFoundError(f"summary.csv ausente: {summary}")
    if not readme.is_file():
        raise FileNotFoundError(f"README.md ausente: {readme}")
    figures = sorted(root.glob("**/*.png"))
    if not figures:
        raise FileNotFoundError(f"Nenhuma figura PNG encontrada em {root}")
    print("=== PLOTS validation ===")
    print(f"WORKSPACE={root}")
    print(f"FIGURES={len(figures)}")
    print("SUCCESS: PLOTS validado.")
    return True


def _product_map(products: BMatrixProducts) -> dict[str, Path]:
    return {key: Path(value) for key, value in asdict(products).items()}


def _summarize_dataset(product_name: str, path: Path, dataset, *, np) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name, variable in dataset.variables.items():
        if not _is_numeric_variable(variable, np=np):
            continue
        values = np.ma.asarray(variable[:], dtype=float).filled(np.nan).ravel()
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            vmin = vmax = mean = rms = max_abs = float("nan")
            nonzero_count = 0
        else:
            vmin = float(np.min(finite))
            vmax = float(np.max(finite))
            mean = float(np.mean(finite))
            rms = float(np.sqrt(np.mean(finite * finite)))
            max_abs = float(np.max(np.abs(finite)))
            nonzero_count = int(np.count_nonzero(finite))
        rows.append(
            {
                "product": product_name,
                "path": str(path),
                "variable": name,
                "shape": "x".join(str(size) for size in variable.shape) or "scalar",
                "min": _format_number(vmin),
                "max": _format_number(vmax),
                "mean": _format_number(mean),
                "rms": _format_number(rms),
                "max_abs": _format_number(max_abs),
                "nonzero_count": nonzero_count,
            }
        )
    return rows


def _plot_dataset(
    product_name: str,
    path: Path,
    dataset,
    root: Path,
    selected: Sequence[str],
    *,
    level: int,
    dpi: int,
    plt,
    np,
) -> list[Path]:
    figures: list[Path] = []
    x, y = _coordinates(dataset, np=np)
    outdir = root / _safe_name(product_name)
    outdir.mkdir(parents=True, exist_ok=True)

    for name in _ordered_plot_variables(dataset.variables, selected):
        variable = dataset.variables[name]
        if not _is_numeric_variable(variable, np=np):
            continue
        values = _select_plot_values(variable, level=level, np=np)
        if values is None:
            continue
        values = np.asarray(values, dtype=float).ravel()
        finite = np.isfinite(values)
        if not finite.any():
            continue

        fig, ax = plt.subplots(figsize=(8, 4.8))
        if x is not None and y is not None and len(x) == len(values) and len(y) == len(values):
            artist = ax.scatter(x[finite], y[finite], c=values[finite], s=4)
            ax.set_xlabel("longitude")
            ax.set_ylabel("latitude")
            ax.set_title(f"{product_name}: {name}")
            fig.colorbar(artist, ax=ax, label=name)
        else:
            ax.plot(np.arange(values.size)[finite], values[finite], linewidth=0.8)
            ax.set_xlabel("index")
            ax.set_ylabel(name)
            ax.set_title(f"{product_name}: {name}")

        figure = outdir / f"{_safe_name(name)}.png"
        fig.tight_layout()
        fig.savefig(figure, dpi=dpi)
        plt.close(fig)
        figures.append(figure)
    return figures


def _ordered_plot_variables(available, selected: Sequence[str]) -> list[str]:
    ordered: list[str] = []
    for name in selected:
        if name in available and name not in ordered:
            ordered.append(name)
    if not ordered:
        for name in available:
            if name not in {"latCell", "lonCell", "latitude", "longitude"}:
                ordered.append(name)
            if len(ordered) >= 3:
                break
    return ordered


def _select_plot_values(variable, *, level: int, np):
    values = np.ma.asarray(variable[:], dtype=float).filled(np.nan)
    dims = tuple(getattr(variable, "dimensions", ()))

    while (
        values.ndim > 0
        and values.shape[0] == 1
        and (not dims or dims[0].lower() in {"time", "date"})
    ):
        values = values[0]
        dims = dims[1:]

    if values.ndim == 0:
        return None
    if values.ndim == 1:
        return values

    if "nCells" in dims and "nVertLevels" in dims:
        cell_axis = dims.index("nCells")
        level_axis = dims.index("nVertLevels")
        lev = max(0, min(int(level), values.shape[level_axis] - 1))
        values = np.take(values, indices=lev, axis=level_axis)
        if values.ndim > 1:
            values = np.moveaxis(values, cell_axis if cell_axis < level_axis else cell_axis - 1, 0)
            values = values.reshape(values.shape[0], -1)[:, 0]
        return values

    if values.ndim == 2:
        lev = max(0, min(int(level), values.shape[-1] - 1))
        return values[:, lev]

    reshaped = values.reshape(values.shape[0], -1)
    return reshaped[:, 0]


def _coordinates(dataset, *, np):
    lon = _maybe_coord(dataset, ("lonCell", "longitude", "lon"), np=np)
    lat = _maybe_coord(dataset, ("latCell", "latitude", "lat"), np=np)
    if lon is None or lat is None:
        return None, None
    lon = np.asarray(lon, dtype=float).ravel()
    lat = np.asarray(lat, dtype=float).ravel()
    if np.nanmax(np.abs(lon)) <= 2 * math.pi + 1.0e-6:
        lon = np.degrees(lon)
    if np.nanmax(np.abs(lat)) <= math.pi + 1.0e-6:
        lat = np.degrees(lat)
    return lon, lat


def _maybe_coord(dataset, names: Iterable[str], *, np):
    for name in names:
        if name in dataset.variables:
            return np.ma.asarray(dataset.variables[name][:], dtype=float).filled(np.nan)
    return None


def _is_numeric_variable(variable, *, np) -> bool:
    return np.issubdtype(np.dtype(variable.dtype), np.number)


def _write_summary_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_readme(
    path: Path,
    products: BMatrixProducts,
    summary_csv: Path,
    figures: Sequence[Path],
    *,
    level: int,
    dpi: int,
) -> None:
    product_lines = "\n".join(f"- `{name}`: `{value}`" for name, value in asdict(products).items())
    figure_lines = "\n".join(f"- `{figure.relative_to(path.parent)}`" for figure in figures[:200])
    if len(figures) > 200:
        figure_lines += f"\n- ... mais {len(figures) - 200} figuras"
    text = f"""# B-matrix plots

Resumo e figuras gerados a partir dos produtos finais da matriz B.

## Configuração

- nível vertical usado: `{level}`
- DPI: `{dpi}`
- resumo CSV: `{summary_csv.name}`

## Produtos lidos

{product_lines}

## Figuras

{figure_lines or "- nenhuma figura gerada"}
"""
    path.write_text(text)


def _format_number(value: float) -> str:
    if math.isnan(value):
        return "nan"
    return f"{value:.12g}"


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value)
