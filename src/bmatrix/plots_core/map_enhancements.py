"""Optional map-background, color-palette and typography enhancements.

This module monkey-patches selected helpers from ``plots_core.runner``. It is
kept separate so the main plotting stage remains usable without Cartopy; when
Cartopy is available, local/global spatial diagnostics gain coastlines and
geographic gridlines. When Cartopy is unavailable, the Matplotlib fallback still
runs.
"""
from __future__ import annotations

from pathlib import Path
import warnings


CONTOUR_LEVELS = 21
DIRAC_LOCAL_DLON = 38.0
DIRAC_LOCAL_DLAT = 28.0
DIRAC_MIN_SIGNAL = 1.0e-10
GLOBAL_MIN_RANGE = 1.0e-12

# Publication-style palettes following SciFig guidance:
# - sequential: ordered magnitude, light-to-dark single hue;
# - diverging: fields centered on zero, blue for negative and muted red for positive.
SCIFIG_SEQUENTIAL = ("#F7FBFF", "#9ECAE1", "#4292C6", "#08519C")
SCIFIG_DIVERGING = ("#2166AC", "#92C5DE", "#F7F7F7", "#F4A582", "#B2182B")

# Typography and figure styling follow the local nature-figure-style convention,
# adapted to diagnostic PNGs that need to remain readable on screen and slides.
FONT_FALLBACKS = ("Arial", "Helvetica", "DejaVu Sans", "Liberation Sans")
TEXT_COLOR = "#111111"
MUTED_TEXT = "#4B5563"
AXIS_COLOR = "#111111"
MAP_LINE = "#374151"
MAP_BORDER = "#6B7280"
GRID_COLOR = "#D7DEE6"
TITLE_SIZE = 17.0
PANEL_TITLE_SIZE = 13.5
AXIS_LABEL_SIZE = 12.0
TICK_LABEL_SIZE = 10.5
COLORBAR_LABEL_SIZE = 12.0
ANNOTATION_SIZE = 8.5
AXIS_WIDTH = 0.8
TICK_LENGTH = 3.6
GRID_WIDTH = 0.55

# DIRAC response maps already have a dedicated local diagnostic in 05_dirac.
# Global DIRAC maps are usually dominated by near-zero fields or offsets and are
# visually misleading, so 06_spatial_fields focuses on spatial diagnostics that
# make sense globally.
GLOBAL_SPATIAL_PRODUCTS = ("stddev", "cor_rh", "cor_rv", "nicas_norm")
GLOBAL_PRODUCT_LABELS = {
    "stddev": "desvio-padrão",
    "cor_rh": "escala horizontal",
    "cor_rv": "escala vertical",
    "nicas_norm": "normalização NICAS",
}


def apply() -> None:
    """Install plotting enhancements on the runner module."""
    from . import runner

    _apply_global_style()
    runner._finish = _finish
    runner._plot_dirac_spatial = _plot_dirac_spatial
    runner._plot_global_spatial = _plot_global_spatial
    runner._plot_spatial_fields = _plot_spatial_fields
    runner._plot_latlev = _plot_latlev


def _apply_global_style() -> None:
    """Apply a Nature-inspired Matplotlib style without adding dependencies."""
    from matplotlib import rcParams

    rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": list(FONT_FALLBACKS),
            "font.size": TICK_LABEL_SIZE,
            "axes.titlesize": PANEL_TITLE_SIZE,
            "axes.titleweight": "bold",
            "axes.labelsize": AXIS_LABEL_SIZE,
            "axes.labelweight": "normal",
            "axes.linewidth": AXIS_WIDTH,
            "axes.edgecolor": AXIS_COLOR,
            "axes.labelcolor": TEXT_COLOR,
            "axes.facecolor": "white",
            "axes.grid": False,
            "xtick.labelsize": TICK_LABEL_SIZE,
            "ytick.labelsize": TICK_LABEL_SIZE,
            "xtick.color": TEXT_COLOR,
            "ytick.color": TEXT_COLOR,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "xtick.major.width": AXIS_WIDTH,
            "ytick.major.width": AXIS_WIDTH,
            "xtick.major.size": TICK_LENGTH,
            "ytick.major.size": TICK_LENGTH,
            "legend.fontsize": TICK_LABEL_SIZE,
            "legend.frameon": False,
            "legend.handlelength": 1.4,
            "legend.borderaxespad": 0.4,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.edgecolor": "white",
            "savefig.transparent": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def _cartopy():
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
    except Exception:  # pragma: no cover - optional runtime dependency
        return None, None
    return ccrs, cfeature


def _scifig_cmap(ctx, kind: str):
    from matplotlib.colors import LinearSegmentedColormap

    if kind == "diverging":
        return LinearSegmentedColormap.from_list("bmatrix_scifig_diverging", SCIFIG_DIVERGING)
    if kind == "sequential":
        return LinearSegmentedColormap.from_list("bmatrix_scifig_sequential", SCIFIG_SEQUENTIAL)
    return ctx.plt.get_cmap(kind)


def _style_axis(axis, *, grid: bool | None = None) -> None:
    """Style one Matplotlib/Cartopy axis with publication-like typography."""
    axis.set_facecolor("white")
    axis.title.set_fontsize(PANEL_TITLE_SIZE)
    axis.title.set_fontweight("bold")
    axis.title.set_color(TEXT_COLOR)
    axis.xaxis.label.set_fontsize(AXIS_LABEL_SIZE)
    axis.yaxis.label.set_fontsize(AXIS_LABEL_SIZE)
    axis.xaxis.label.set_color(TEXT_COLOR)
    axis.yaxis.label.set_color(TEXT_COLOR)
    axis.tick_params(
        axis="both",
        which="major",
        labelsize=TICK_LABEL_SIZE,
        width=AXIS_WIDTH,
        length=TICK_LENGTH,
        direction="out",
        colors=TEXT_COLOR,
    )
    axis.tick_params(
        axis="both",
        which="minor",
        width=max(AXIS_WIDTH * 0.75, 0.35),
        length=max(TICK_LENGTH * 0.6, 1.5),
        direction="out",
        colors=TEXT_COLOR,
    )
    if grid is not None:
        axis.grid(grid, color=GRID_COLOR, linewidth=GRID_WIDTH, linestyle=":", alpha=0.9)
    for spine in axis.spines.values():
        spine.set_linewidth(AXIS_WIDTH)
        spine.set_color(AXIS_COLOR)
    legend = axis.get_legend()
    if legend is not None:
        legend.set_frame_on(False)
        for text in legend.get_texts():
            text.set_color(TEXT_COLOR)
            text.set_fontsize(TICK_LABEL_SIZE)


def _style_figure(fig) -> None:
    fig.patch.set_facecolor("white")
    if fig._suptitle is not None:
        fig._suptitle.set_fontsize(TITLE_SIZE)
        fig._suptitle.set_fontweight("bold")
        fig._suptitle.set_color(TEXT_COLOR)
    for axis in fig.get_axes():
        _style_axis(axis, grid=None)


def _style_colorbar(colorbar, label: str | None = None) -> None:
    if label is not None:
        colorbar.set_label(label, fontsize=COLORBAR_LABEL_SIZE, color=TEXT_COLOR, labelpad=10)
    colorbar.ax.tick_params(
        labelsize=TICK_LABEL_SIZE,
        width=AXIS_WIDTH,
        length=TICK_LENGTH,
        direction="out",
        colors=TEXT_COLOR,
    )
    colorbar.outline.set_linewidth(AXIS_WIDTH)
    colorbar.outline.set_edgecolor(AXIS_COLOR)


def _finish(fig, output, dpi: int, ctx) -> None:
    """Save a figure while avoiding tight_layout warnings for complex axes."""
    output.parent.mkdir(parents=True, exist_ok=True)
    _style_figure(fig)
    skip_tight = bool(getattr(fig, "_bmatrix_skip_tight_layout", False))
    constrained = False
    try:
        constrained = bool(fig.get_constrained_layout())
    except Exception:
        constrained = False

    if not skip_tight and not constrained:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="This figure includes Axes that are not compatible with tight_layout.*",
                category=UserWarning,
            )
            try:
                rect = (0.0, 0.0, 1.0, 0.94) if fig._suptitle else None
                fig.tight_layout(rect=rect)
            except Exception:
                pass

    if skip_tight or constrained:
        fig.savefig(output, dpi=dpi)
    else:
        fig.savefig(output, dpi=dpi, bbox_inches="tight")
    ctx.plt.close(fig)


def _add_map_background(axis, *, extent=None, global_map: bool = False, transform=None):
    ccrs, cfeature = _cartopy()
    if ccrs is None:
        _style_axis(axis, grid=True)
        return None

    plate = transform or ccrs.PlateCarree()
    try:
        if global_map:
            axis.set_global()
        elif extent is not None:
            axis.set_extent(extent, crs=plate)
        axis.add_feature(cfeature.LAND, facecolor="#F3F4F6", edgecolor="none", zorder=0)
        axis.add_feature(cfeature.OCEAN, facecolor="white", edgecolor="none", zorder=0)
        axis.coastlines(resolution="110m", linewidth=0.8, color=MAP_LINE, zorder=5)
        axis.add_feature(cfeature.BORDERS, linewidth=0.35, edgecolor=MAP_BORDER, zorder=5)
        gridlines = axis.gridlines(
            draw_labels=True,
            linewidth=0.45,
            linestyle=":",
            color=GRID_COLOR,
            alpha=0.9,
        )
        gridlines.top_labels = False
        gridlines.right_labels = False
        gridlines.xlabel_style = {"size": TICK_LABEL_SIZE, "color": TEXT_COLOR}
        gridlines.ylabel_style = {"size": TICK_LABEL_SIZE, "color": TEXT_COLOR}
    except Exception:
        _style_axis(axis, grid=True)
        return None
    return plate


def _plot_latlev(
    latlev,
    lat,
    title: str,
    label: str,
    unit: str,
    output: Path,
    dpi: int,
    ctx,
) -> None:
    """Latitude-level plot using publication-style sequential/diverging palettes."""
    from . import runner

    values = ctx.np.asarray(latlev, dtype=float)
    lat = ctx.np.asarray(lat, dtype=float)
    finite = values[ctx.np.isfinite(values)]
    if finite.size == 0:
        return

    vmin, vmax, kind = _limits_and_palette_kind(finite, ctx.np)
    levels = ctx.np.linspace(vmin, vmax, 17)
    cmap = _scifig_cmap(ctx, kind)

    fig, axis = ctx.plt.subplots(figsize=(8.4, 5.6))
    image = axis.contourf(
        lat,
        ctx.np.arange(values.shape[0]),
        ctx.np.ma.masked_invalid(values),
        levels=levels,
        cmap=cmap,
        extend="both",
    )
    lines = axis.contour(
        lat,
        ctx.np.arange(values.shape[0]),
        ctx.np.ma.masked_invalid(values),
        levels=levels[::4],
        colors=MAP_LINE,
        linewidths=0.55,
        alpha=0.65,
    )
    axis.clabel(lines, inline=True, fontsize=TICK_LABEL_SIZE - 1, fmt="%.2g", colors=MUTED_TEXT)
    axis.set_title(f"{title} — {label}", pad=10)
    axis.set_xlabel("Latitude (°)")
    axis.set_ylabel("Nível vertical")
    _style_axis(axis, grid=True)
    colorbar = fig.colorbar(image, ax=axis, pad=0.018, fraction=0.048)
    _style_colorbar(colorbar, unit)
    runner._finish(fig, output, dpi, ctx)


def _plot_dirac_spatial(
    name: str,
    lon,
    lat,
    levels,
    fields,
    output,
    dpi: int,
    ctx,
) -> None:
    from . import runner

    np = ctx.np
    lon = np.asarray(lon, dtype=float).ravel()
    lat = np.asarray(lat, dtype=float).ravel()
    raw_fields = [np.asarray(field, dtype=float).ravel() for field in fields]

    center_field = raw_fields[len(raw_fields) // 2]
    finite_center = np.isfinite(center_field)
    if not finite_center.any():
        return
    peak = int(np.nanargmax(np.abs(np.where(finite_center, center_field, np.nan))))
    lon0 = float(lon[peak])
    lat0 = float(lat[peak])
    local_lon = ((lon - lon0 + 180.0) % 360.0) - 180.0

    dlon = DIRAC_LOCAL_DLON
    dlat = DIRAC_LOCAL_DLAT
    local = (np.abs(local_lon) <= dlon) & (lat >= lat0 - dlat) & (lat <= lat0 + dlat)
    if not local.any():
        return

    display_fields = [_remove_local_baseline(field, local, np) for field in raw_fields]
    local_chunks = [field[local] for field in display_fields]
    maximum = _robust_abs_limit(local_chunks, np)
    if maximum < DIRAC_MIN_SIGNAL:
        return

    ccrs, _ = _cartopy()
    has_map = ccrs is not None
    plate = ccrs.PlateCarree() if has_map else None
    projection = ccrs.PlateCarree(central_longitude=lon0) if has_map else None

    fig = ctx.plt.figure(figsize=(16.8, 5.9))
    fig._bmatrix_skip_tight_layout = True
    grid = fig.add_gridspec(
        1,
        len(levels) + 1,
        width_ratios=[1.0] * len(levels) + [0.055],
        left=0.045,
        right=0.935,
        bottom=0.14,
        top=0.80,
        wspace=0.08,
    )
    if has_map:
        axes = [fig.add_subplot(grid[0, index], projection=projection) for index in range(len(levels))]
    else:
        axes = [fig.add_subplot(grid[0, index]) for index in range(len(levels))]
    colorbar_axis = fig.add_subplot(grid[0, -1])

    label = runner.CONTROL_LABELS.get(name, name)
    fig.suptitle(f"Resposta espacial da B: {label} a um impulso em $T_u$ (DIRAC)", y=0.955)
    norm = ctx.plt.Normalize(vmin=-maximum, vmax=maximum)
    cmap = _scifig_cmap(ctx, "diverging")
    artist = None

    for axis, field, item in zip(axes, display_fields, levels):
        signal = local & np.isfinite(field)
        if not signal.any():
            axis.set_axis_off()
            continue
        if has_map:
            extent = [lon0 - dlon, lon0 + dlon, lat0 - dlat, lat0 + dlat]
            transform = _add_map_background(axis, extent=extent, transform=plate)
            artist = _spatial_artist(
                axis,
                lon[signal],
                lat[signal],
                field[signal],
                norm,
                ctx,
                cmap=cmap,
                transform=transform,
            )
            scatter_kwargs = {"transform": transform} if transform is not None else {}
            axis.scatter(
                [lon0],
                [lat0],
                marker="x",
                s=105,
                color=TEXT_COLOR,
                linewidths=2.2,
                zorder=6,
                **scatter_kwargs,
            )
        else:
            artist = _spatial_artist(
                axis,
                local_lon[signal],
                lat[signal],
                field[signal],
                norm,
                ctx,
                cmap=cmap,
                transform=None,
            )
            axis.scatter([0.0], [lat0], marker="x", s=105, color=TEXT_COLOR, linewidths=2.2)
            axis.set_xlabel("Longitude relativa ao impulso (°)")
            axis.set_xlim(-dlon, dlon)
            axis.set_ylim(lat0 - dlat, lat0 + dlat)
            _style_axis(axis, grid=True)

        axis.set_title("2D/superfície" if item is None else f"Nível {item}", pad=8)

    axes[0].set_ylabel("Latitude (°)")
    if artist is not None:
        colorbar = fig.colorbar(artist, cax=colorbar_axis)
        _style_colorbar(colorbar, f"Resposta em {label}")
    fig.text(
        0.01,
        0.035,
        f"Impulso: {lat0:.1f}°, {lon0:.1f}°",
        fontsize=ANNOTATION_SIZE,
        color=MUTED_TEXT,
        ha="left",
        va="bottom",
    )
    _finish(fig, output, dpi, ctx)


def _plot_spatial_fields(
    products,
    root,
    selected,
    level: int,
    dpi: int,
    ctx,
) -> list[Path]:
    """Generate only informative global spatial maps.

    DIRAC products are intentionally omitted here because the local DIRAC response
    is already generated in ``05_dirac`` and is much easier to interpret.
    """
    from . import runner

    outdir = root / "06_spatial_fields"
    outdir.mkdir(parents=True, exist_ok=True)
    figures: list[Path] = []

    product_map = {
        "stddev": products.stddev,
        "cor_rh": products.cor_rh,
        "cor_rv": products.cor_rv,
        "nicas_norm": products.nicas_norm,
    }

    for product_name in GLOBAL_SPATIAL_PRODUCTS:
        product_path = Path(product_map[product_name])
        if not product_path.is_file():
            continue
        with ctx.netcdf4.Dataset(product_path) as dataset:
            for name in runner._ordered_plot_variables(dataset.variables, selected):
                if name not in dataset.variables:
                    continue
                variable = dataset.variables[name]
                if not runner._is_numeric_variable(variable, ctx=ctx):
                    continue
                levels, fields = runner._spatial_levels(variable, level, ctx=ctx)
                if not fields:
                    continue
                for item, field in zip(levels, fields):
                    values = ctx.np.asarray(field, dtype=float).ravel()
                    if not _is_informative(values, ctx.np, abs_tol=GLOBAL_MIN_RANGE):
                        continue
                    lon, lat = runner._coordinates_for_size(
                        products,
                        len(values),
                        ctx=ctx,
                        dataset=dataset,
                    )
                    if lon is None or lat is None:
                        continue
                    level_name = "surface" if item is None else f"lev{item:02d}"
                    figure = outdir / f"{product_name}_{runner._safe_name(name)}_{level_name}_spatial.png"
                    _plot_global_spatial(product_name, name, lon, lat, values, item, figure, dpi, ctx)
                    figures.append(figure)

    return figures


def _plot_global_spatial(
    product_name: str,
    variable_name: str,
    lon,
    lat,
    field,
    level,
    output,
    dpi: int,
    ctx,
) -> None:
    from . import runner

    np = ctx.np
    values = np.asarray(field, dtype=float).ravel()
    lon = np.asarray(lon, dtype=float).ravel()
    lat = np.asarray(lat, dtype=float).ravel()
    finite = np.isfinite(values) & np.isfinite(lon) & np.isfinite(lat)
    if not finite.any():
        return

    finite_values = values[finite]
    if not _is_informative(finite_values, np, abs_tol=GLOBAL_MIN_RANGE):
        return
    vmin, vmax, kind = _global_limits_and_cmap(finite_values, np)
    norm = ctx.plt.Normalize(vmin=vmin, vmax=vmax)
    cmap = _scifig_cmap(ctx, kind)

    ccrs, _ = _cartopy()
    has_map = ccrs is not None
    plate = ccrs.PlateCarree() if has_map else None

    fig = ctx.plt.figure(figsize=(12.4, 5.9))
    fig._bmatrix_skip_tight_layout = True
    grid = fig.add_gridspec(
        1,
        2,
        width_ratios=[1.0, 0.038],
        left=0.07,
        right=0.91,
        bottom=0.12,
        top=0.80,
        wspace=0.055,
    )
    if has_map:
        axis = fig.add_subplot(grid[0, 0], projection=plate)
        transform = _add_map_background(axis, global_map=True, transform=plate)
    else:
        axis = fig.add_subplot(grid[0, 0])
        transform = None
        axis.set_xlim(-180.0, 180.0)
        axis.set_ylim(-90.0, 90.0)
        _style_axis(axis, grid=True)
    colorbar_axis = fig.add_subplot(grid[0, 1])

    artist = _spatial_artist(
        axis,
        lon[finite],
        lat[finite],
        finite_values,
        norm,
        ctx,
        cmap=cmap,
        transform=transform,
    )

    label = runner.CONTROL_LABELS.get(variable_name, variable_name)
    product_label = GLOBAL_PRODUCT_LABELS.get(product_name, product_name)
    level_label = "2D/superfície" if level is None else f"Nível {level}"
    fig.suptitle(f"Campo espacial da B: {label} — {product_label}", y=0.955)
    axis.set_title(level_label, pad=8)
    if not has_map:
        axis.set_xlabel("Longitude (°)")
        axis.set_ylabel("Latitude (°)")
    colorbar = fig.colorbar(artist, cax=colorbar_axis)
    _style_colorbar(colorbar, label)
    _finish(fig, output, dpi, ctx)


def _remove_local_baseline(field, local, np):
    values = np.asarray(field, dtype=float).copy()
    finite_local = values[local & np.isfinite(values)]
    if finite_local.size == 0:
        return values
    baseline = float(np.nanmedian(finite_local))
    return values - baseline


def _robust_abs_limit(fields, np) -> float:
    chunks = []
    for field in fields:
        values = np.asarray(field, dtype=float).ravel()
        finite = values[np.isfinite(values)]
        if finite.size:
            chunks.append(np.abs(finite))
    if not chunks:
        return 0.0
    values = np.concatenate(chunks)
    if values.size == 0:
        return 0.0
    limit = float(np.nanpercentile(values, 99.0))
    if not np.isfinite(limit) or limit <= 0.0:
        limit = float(np.nanmax(values))
    return limit * 1.05 if np.isfinite(limit) else 0.0


def _limits_and_palette_kind(values, np):
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return -1.0, 1.0, "diverging"
    vmin = float(np.nanpercentile(finite, 2.0))
    vmax = float(np.nanpercentile(finite, 98.0))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        vmin = float(np.nanmin(finite))
        vmax = float(np.nanmax(finite))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        center = 0.0 if not np.isfinite(vmin) else vmin
        return center - 1.0, center + 1.0, "sequential"
    if vmin < 0.0 < vmax:
        amplitude = max(abs(vmin), abs(vmax))
        return -amplitude, amplitude, "diverging"
    return vmin, vmax, "sequential"


def _global_limits_and_cmap(values, np):
    return _limits_and_palette_kind(values, np)


def _is_informative(values, np, *, abs_tol: float) -> bool:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return False
    spread = float(np.nanpercentile(finite, 98.0) - np.nanpercentile(finite, 2.0))
    amplitude = float(np.nanmax(np.abs(finite)))
    if not np.isfinite(spread) or not np.isfinite(amplitude):
        return False
    if amplitude < abs_tol:
        return False
    return spread > max(abs_tol, amplitude * 1.0e-8)


def _spatial_artist(axis, x, y, values, norm, ctx, *, cmap="diverging", transform=None):
    values = ctx.np.asarray(values, dtype=float)
    kwargs = {"transform": transform} if transform is not None else {}
    if isinstance(cmap, str):
        cmap = _scifig_cmap(ctx, cmap)
    levels = ctx.np.linspace(norm.vmin, norm.vmax, CONTOUR_LEVELS)
    if len(values) >= 20:
        try:
            triangulation = ctx.mtri.Triangulation(x, y)
            return axis.tricontourf(
                triangulation,
                values,
                levels=levels,
                cmap=cmap,
                norm=norm,
                extend="both",
                **kwargs,
            )
        except (TypeError, ValueError, RuntimeError):
            pass
    return axis.scatter(x, y, c=values, s=8, cmap=cmap, norm=norm, linewidths=0, zorder=3, **kwargs)
