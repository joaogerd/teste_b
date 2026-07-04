from __future__ import annotations

import argparse
import html
import re
from datetime import datetime
from pathlib import Path

DEFAULT_FILES = ("mpas.stddev.nc", "mpas.cor_rh.nc", "mpas.cor_rv.nc")
DEFAULT_VARIABLES = (
    "stream_function",
    "velocity_potential",
    "temperature",
    "spechum",
    "surface_pressure",
)


def safe_stem(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "field"


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def finite(values):
    import numpy as np

    arr = np.ma.asarray(values, dtype=float).filled(np.nan)
    arr = np.asarray(arr, dtype=float)
    arr[np.abs(arr) > 1.0e30] = np.nan
    return arr


def stats(values) -> str:
    import numpy as np

    arr = finite(values)
    good = arr[np.isfinite(arr)]
    if good.size == 0:
        return "finite=0"
    return (
        f"finite={good.size}, min={np.nanmin(good):.6g}, max={np.nanmax(good):.6g}, "
        f"mean={np.nanmean(good):.6g}, rms={np.sqrt(np.nanmean(good * good)):.6g}, "
        f"nonzero={np.count_nonzero(good)}"
    )


def iter_variables(dataset):
    for name, variable in dataset.variables.items():
        yield name, variable


def is_numeric(variable) -> bool:
    import numpy as np

    return np.issubdtype(np.dtype(variable.dtype), np.number)


def is_supported_field(variable) -> bool:
    dims = tuple(variable.dimensions)
    if not is_numeric(variable):
        return False
    if "nCells" not in dims:
        return False
    return True


def field_array(variable):
    arr = finite(variable[:])
    dims = tuple(variable.dimensions)
    if "Time" in dims:
        axis = dims.index("Time")
        arr = arr.take(indices=0, axis=axis)
        dims = tuple(dim for dim in dims if dim != "Time")
    return arr, dims


def profile_from_field(arr, dims):
    import numpy as np

    if "nVertLevels" not in dims or "nCells" not in dims:
        return None
    level_axis = dims.index("nVertLevels")
    cell_axis = dims.index("nCells")
    arr = np.moveaxis(arr, (level_axis, cell_axis), (0, 1))
    return np.nanmean(arr, axis=1)


def level_map_from_field(arr, dims, level: int):
    if "nCells" not in dims:
        return None
    if "nVertLevels" in dims:
        level_axis = dims.index("nVertLevels")
        max_level = arr.shape[level_axis] - 1
        level = min(max(level, 0), max_level)
        arr = arr.take(indices=level, axis=level_axis)
        dims = tuple(dim for dim in dims if dim != "nVertLevels")
    if tuple(dims) == ("nCells",):
        return finite(arr)
    return None


def plot_profile(profile, path: Path, title: str, label: str, dpi: int) -> bool:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    if profile is None or not np.isfinite(profile).any():
        return False
    fig, ax = plt.subplots(figsize=(5, 7))
    ax.plot(profile, np.arange(profile.size))
    ax.set_title(title)
    ax.set_xlabel(label)
    ax.set_ylabel("vertical level")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return True


def plot_histogram(values, path: Path, title: str, label: str, dpi: int) -> bool:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    arr = finite(values)
    good = arr[np.isfinite(arr)]
    if good.size == 0:
        return False
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(good, bins=80)
    ax.set_title(title)
    ax.set_xlabel(label)
    ax.set_ylabel("count")
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return True


def plot_cell_values(values, path: Path, title: str, label: str, dpi: int) -> bool:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    arr = finite(values)
    if arr.ndim != 1 or not np.isfinite(arr).any():
        return False
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(np.arange(arr.size), arr, linewidth=0.8)
    ax.set_title(title)
    ax.set_xlabel("cell index")
    ax.set_ylabel(label)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return True


def add_figure(figures: list[Path], figure: Path, created: bool) -> None:
    if created and figure.is_file():
        figures.append(figure)


def write_html_index(output: Path, figures: list[Path], report: Path) -> Path:
    index = output / "index.html"
    rows = [
        "<!doctype html>",
        "<html>",
        "<head>",
        '<meta charset="utf-8">',
        "<title>HDIAG diagnostics</title>",
        "<style>",
        "body{font-family:Arial,sans-serif;margin:24px;}",
        "img{max-width:1100px;width:100%;border:1px solid #ddd;margin:8px 0 28px 0;}",
        "code{background:#eee;padding:2px 4px;}",
        "</style>",
        "</head>",
        "<body>",
        "<h1>HDIAG diagnostics</h1>",
        f"<p>Generated: <code>{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}</code></p>",
        f'<p>Markdown report: <a href="{html.escape(report.name)}">{html.escape(report.name)}</a></p>',
    ]
    for figure in figures:
        rows.append(f"<h2>{html.escape(figure.name)}</h2>")
        rows.append(f'<img src="{html.escape(figure.name)}" alt="{html.escape(figure.name)}">')
    rows.extend(["</body>", "</html>", ""])
    index.write_text("\n".join(rows), encoding="utf-8")
    return index


def candidate_files(workspace: Path, requested: list[str]) -> list[Path]:
    root = workspace / "HDIAG"
    if requested:
        return [root / item for item in requested]
    files = [root / item for item in DEFAULT_FILES]
    return [path for path in files if path.is_file()]


def summarize_hdiag(
    workspace: str | Path,
    output_dir: str | Path | None = None,
    level: int = 30,
    dpi: int = 150,
    variables: list[str] | None = None,
    files: list[str] | None = None,
    mode: str = "quick",
) -> list[Path]:
    import netCDF4

    workspace = Path(workspace)
    output = Path(output_dir) if output_dir else workspace / "HDIAG" / "figures_hdiag_summary"
    output.mkdir(parents=True, exist_ok=True)
    active_variables = set(variables or DEFAULT_VARIABLES)
    use_all_variables = variables == []
    use_histograms = mode in {"standard", "full"}
    figures: list[Path] = []
    lines = [
        "# HDIAG summary diagnostics",
        "",
        f"Workspace: `{workspace}`",
        f"Mode: `{mode}`",
        f"Level: `{level}`",
        f"Variables: `{sorted(active_variables) if not use_all_variables else 'all'}`",
        "",
        "| file | variable | dims | shape | stats | products |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for path in candidate_files(workspace, files or []):
        if not path.is_file():
            lines.append(f"| {path.name} | MISSING | | | | |")
            continue
        with netCDF4.Dataset(path) as ds:
            for name, variable in iter_variables(ds):
                if not is_supported_field(variable):
                    continue
                if not use_all_variables and name not in active_variables:
                    continue
                arr, dims = field_array(variable)
                stem = f"hdiag_{safe_stem(path.stem)}_{safe_stem(name)}"
                made: list[Path] = []
                profile = profile_from_field(arr, dims)
                fig = output / f"{stem}_profile.png"
                add_figure(made, fig, plot_profile(profile, fig, f"{path.name} {name} profile", name, dpi))
                level_values = level_map_from_field(arr, dims, level)
                fig = output / f"{stem}_level{level:02d}_cell_series.png"
                add_figure(made, fig, plot_cell_values(level_values, fig, f"{path.name} {name} level {level}", name, dpi))
                if use_histograms:
                    fig = output / f"{stem}_histogram.png"
                    add_figure(made, fig, plot_histogram(arr, fig, f"{path.name} {name} histogram", name, dpi))
                figures.extend(made)
                products = ", ".join(f"[{item.name}]({item.name})" for item in made)
                lines.append(f"| {path.name} | {name} | `{tuple(variable.dimensions)}` | `{tuple(variable.shape)}` | {stats(variable[:])} | {products} |")
    report = output / "hdiag_summary.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    index = write_html_index(output, figures, report)
    print(f"REPORT={report}")
    print(f"HTML_INDEX={index}")
    for figure in figures:
        print(f"FIGURE={figure}")
    return figures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize HDIAG NetCDF products")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--level", type=int, default=30)
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--mode", choices=["quick", "standard", "full"], default="quick")
    parser.add_argument("--variables", help="Comma-separated variables. Use 'all' for all supported nCells fields.")
    parser.add_argument("--files", help="Comma-separated HDIAG file names under workspace/HDIAG.")
    args = parser.parse_args(argv)
    variables = None
    if args.variables:
        variables = [] if args.variables.strip().lower() == "all" else parse_csv(args.variables)
    summarize_hdiag(
        args.workspace,
        output_dir=args.output_dir,
        level=args.level,
        dpi=args.dpi,
        variables=variables,
        files=parse_csv(args.files),
        mode=args.mode,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
