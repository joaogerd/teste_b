from __future__ import annotations

import argparse
import html
import re
from datetime import datetime
from pathlib import Path

LAT_BANDS = [(-90, -60), (-60, -30), (-30, 0), (0, 30), (30, 60), (60, 90)]
DEFAULT_PAIRS = {
    "stream_function-velocity_potential",
    "stream_function-temperature",
    "stream_function-surface_pressure",
}
DEFAULT_PRODUCTS = {"explained", "reg"}


def safe_stem(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "field"


def parse_csv_set(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def iter_group_variables(group, prefix: str = ""):
    for name, variable in group.variables.items():
        yield prefix, name, variable
    for name, child in group.groups.items():
        child_prefix = f"{prefix}/{name}" if prefix else name
        yield from iter_group_variables(child, child_prefix)


def finite(values):
    import numpy as np

    arr = np.ma.asarray(values, dtype=float).filled(np.nan)
    arr[np.abs(arr) > 1.0e30] = np.nan
    return arr


def load_lat_c2(workspace: Path):
    import netCDF4
    import numpy as np

    path = workspace / "VBAL" / "mpas_sampling.nc"
    with netCDF4.Dataset(path) as ds:
        lat = finite(ds.variables["lat_c2"][:])
    if lat.size and np.nanmax(np.abs(lat)) <= np.pi + 0.1:
        lat = np.degrees(lat)
    return lat


def product_kind(variable_name: str) -> str | None:
    if variable_name.startswith("explained_var"):
        return "explained"
    if variable_name.startswith("reg"):
        return "reg"
    if variable_name.startswith("cov"):
        return "cov"
    return None


def should_process(group_name: str, variable_name: str, pairs: set[str], products: set[str]) -> bool:
    kind = product_kind(variable_name)
    if kind is None:
        return False
    if pairs and group_name not in pairs:
        return False
    return kind in products


def diagonal_levels(values):
    import numpy as np

    arr = finite(values)
    if arr.ndim != 3 or arr.shape[0] != arr.shape[1]:
        return None
    diag = np.diagonal(arr, axis1=0, axis2=1)
    if diag.shape[0] == arr.shape[2]:
        diag = diag.T
    return diag


def matrix_mean(values, lat=None, band=None):
    import numpy as np

    arr = finite(values)
    if arr.ndim != 3:
        return None
    if lat is not None and band is not None:
        lo, hi = band
        mask = (lat >= lo) & ((lat < hi) if hi < 90 else (lat <= hi))
        if not np.any(mask):
            return None
        arr = arr[:, :, mask]
    return np.nanmean(arr, axis=2)


def band_masks(lat):
    masks = []
    for lo, hi in LAT_BANDS:
        mask = (lat >= lo) & ((lat < hi) if hi < 90 else (lat <= hi))
        if mask.any():
            masks.append((lo, hi, mask))
    return masks


def plot_lat_level(values, lat, path: Path, title: str, label: str, dpi: int) -> bool:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    arr = finite(values)
    order = np.argsort(lat)
    arr = arr[:, order]
    lat = lat[order]
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return False
    cmap = "coolwarm" if np.nanmin(valid) < 0 and np.nanmax(valid) > 0 else "viridis"
    fig, ax = plt.subplots(figsize=(9, 5))
    image = ax.imshow(
        arr,
        origin="lower",
        aspect="auto",
        cmap=cmap,
        extent=[float(lat[0]), float(lat[-1]), 0, arr.shape[0] - 1],
    )
    ax.set_title(title)
    ax.set_xlabel("latitude")
    ax.set_ylabel("vertical level")
    fig.colorbar(image, ax=ax, label=label)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return True


def plot_profile(values, path: Path, title: str, label: str, dpi: int) -> bool:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    arr = finite(values)
    profile = np.nanmean(arr, axis=1) if arr.ndim == 2 else arr
    if not np.isfinite(profile).any():
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


def plot_band_profiles(values, lat, path: Path, title: str, label: str, dpi: int) -> bool:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    arr = finite(values)
    fig, ax = plt.subplots(figsize=(6, 7))
    count = 0
    for lo, hi, mask in band_masks(lat):
        profile = np.nanmean(arr[:, mask], axis=1)
        if np.isfinite(profile).any():
            ax.plot(profile, np.arange(profile.size), label=f"{lo} to {hi}")
            count += 1
    if count == 0:
        plt.close(fig)
        return False
    ax.set_title(title)
    ax.set_xlabel(label)
    ax.set_ylabel("vertical level")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize="small")
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return True


def plot_matrix(values, path: Path, title: str, label: str, dpi: int) -> bool:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    arr = finite(values)
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return False
    cmap = "coolwarm" if np.nanmin(valid) < 0 and np.nanmax(valid) > 0 else "viridis"
    fig, ax = plt.subplots(figsize=(6, 5.5))
    image = ax.imshow(arr, origin="lower", aspect="auto", cmap=cmap)
    ax.set_title(title)
    ax.set_xlabel("vertical level 1")
    ax.set_ylabel("vertical level 2")
    fig.colorbar(image, ax=ax, label=label)
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
        "<title>VBAL grouped diagnostics</title>",
        "<style>",
        "body{font-family:Arial,sans-serif;margin:24px;}",
        "img{max-width:1100px;width:100%;border:1px solid #ddd;margin:8px 0 28px 0;}",
        "code{background:#eee;padding:2px 4px;}",
        "</style>",
        "</head>",
        "<body>",
        "<h1>VBAL grouped diagnostics</h1>",
        f"<p>Generated: <code>{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}</code></p>",
        f'<p>Markdown report: <a href="{html.escape(report.name)}">{html.escape(report.name)}</a></p>',
    ]
    for figure in figures:
        rows.append(f"<h2>{html.escape(figure.name)}</h2>")
        rows.append(f'<img src="{html.escape(figure.name)}" alt="{html.escape(figure.name)}">')
    rows.extend(["</body>", "</html>", ""])
    index.write_text("\n".join(rows), encoding="utf-8")
    return index


def plot_vbal_groups(
    workspace: str | Path,
    output_dir: str | Path | None = None,
    dpi: int = 150,
    mode: str = "quick",
    pairs: set[str] | None = None,
    products: set[str] | None = None,
) -> list[Path]:
    import netCDF4

    workspace = Path(workspace)
    output = Path(output_dir) if output_dir else workspace / "VBAL" / "figures_vbal_groups"
    output.mkdir(parents=True, exist_ok=True)
    lat = load_lat_c2(workspace)
    vbal = workspace / "VBAL" / "mpas_vbal.nc"
    if mode not in {"quick", "standard", "full"}:
        raise ValueError("mode must be quick, standard or full")
    active_pairs = pairs if pairs is not None else DEFAULT_PAIRS
    active_products = products if products is not None else DEFAULT_PRODUCTS
    use_latbands = mode in {"standard", "full"}
    use_matrices = mode == "full"

    figures: list[Path] = []
    lines = [
        "# VBAL grouped diagnostics",
        "",
        f"Workspace: `{workspace}`",
        f"Mode: `{mode}`",
        f"Pairs: `{sorted(active_pairs) if active_pairs else 'all'}`",
        f"Products: `{sorted(active_products)}`",
        "",
        "| group | variable | shape | products |",
        "| --- | --- | --- | --- |",
    ]
    with netCDF4.Dataset(vbal) as ds:
        for group_name, variable_name, variable in iter_group_variables(ds):
            if not should_process(group_name, variable_name, active_pairs, active_products):
                continue
            values = finite(variable[:])
            stem = f"vbal_{safe_stem(group_name)}_{safe_stem(variable_name)}"
            made: list[Path] = []
            if variable_name.startswith("explained_var") and values.ndim == 2:
                fig = output / f"{stem}_lat_level.png"
                add_figure(made, fig, plot_lat_level(values, lat, fig, f"{group_name} {variable_name}", variable_name, dpi))
                fig = output / f"{stem}_profile.png"
                add_figure(made, fig, plot_profile(values, fig, f"Mean profile {group_name} {variable_name}", variable_name, dpi))
                if use_latbands:
                    fig = output / f"{stem}_latband_profiles.png"
                    add_figure(made, fig, plot_band_profiles(values, lat, fig, f"Latitude-band profiles {group_name} {variable_name}", variable_name, dpi))
            elif variable_name.startswith(("reg", "cov")) and values.ndim == 3:
                diag = diagonal_levels(values)
                if diag is not None:
                    fig = output / f"{stem}_diag_lat_level.png"
                    add_figure(made, fig, plot_lat_level(diag, lat, fig, f"Diagonal {group_name} {variable_name}", variable_name, dpi))
                    fig = output / f"{stem}_diag_profile.png"
                    add_figure(made, fig, plot_profile(diag, fig, f"Mean diagonal profile {group_name} {variable_name}", variable_name, dpi))
                    if use_latbands:
                        fig = output / f"{stem}_diag_latband_profiles.png"
                        add_figure(made, fig, plot_band_profiles(diag, lat, fig, f"Latitude-band diagonal profiles {group_name} {variable_name}", variable_name, dpi))
                if use_matrices:
                    mean_mat = matrix_mean(values)
                    if mean_mat is not None:
                        fig = output / f"{stem}_mean_matrix.png"
                        add_figure(made, fig, plot_matrix(mean_mat, fig, f"Mean matrix {group_name} {variable_name}", variable_name, dpi))
                        for band in LAT_BANDS:
                            band_mat = matrix_mean(values, lat=lat, band=band)
                            if band_mat is None:
                                continue
                            lo, hi = band
                            fig = output / f"{stem}_mean_matrix_lat_{lo}_{hi}.png".replace("-", "m")
                            add_figure(made, fig, plot_matrix(band_mat, fig, f"Mean matrix {group_name} {variable_name} lat {lo} to {hi}", variable_name, dpi))
            figures.extend(made)
            products_md = ", ".join(f"[{item.name}]({item.name})" for item in made)
            lines.append(f"| {group_name} | {variable_name} | `{values.shape}` | {products_md} |")
    report = output / "vbal_group_diagnostics.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    index = write_html_index(output, figures, report)
    print(f"REPORT={report}")
    print(f"HTML_INDEX={index}")
    for figure in figures:
        print(f"FIGURE={figure}")
    return figures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plot grouped variables in VBAL/mpas_vbal.nc")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--mode", choices=["quick", "standard", "full"], default="quick")
    parser.add_argument("--pairs", help="Comma-separated group names. Default: three stream_function balance pairs. Use 'all' for all groups.")
    parser.add_argument("--products", help="Comma-separated products: explained,reg,cov. Default: explained,reg.")
    args = parser.parse_args(argv)
    pairs = None
    if args.pairs:
        pairs = set() if args.pairs.strip().lower() == "all" else parse_csv_set(args.pairs)
    products = parse_csv_set(args.products) if args.products else None
    plot_vbal_groups(
        args.workspace,
        output_dir=args.output_dir,
        dpi=args.dpi,
        mode=args.mode,
        pairs=pairs,
        products=products,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
