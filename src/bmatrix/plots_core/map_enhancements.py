"""Optional map-background enhancements for B-matrix plotting.

This module monkey-patches selected helpers from ``plots_core.runner``. It is
kept separate so the main plotting stage remains usable without Cartopy; when
Cartopy is available, local/global spatial diagnostics gain coastlines and
geographic gridlines. When Cartopy is unavailable, the original Matplotlib
fallback still runs.
"""
from __future__ import annotations

import warnings


CONTOUR_LEVELS = 21
DIRAC_LOCAL_DLON = 38.0
DIRAC_LOCAL_DLAT = 28.0


def apply() -> None:
    """Install plotting enhancements on the runner module."""
    from . import runner

    runner._finish = _finish
    runner._plot_dirac_spatial = _plot_dirac_spatial
    runner._plot_global_spatial = _plot_global_spatial


def _cartopy():
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
    except Exception:  # pragma: no cover - optional runtime dependency
        return None, None
    return ccrs, cfeature


def _finish(fig, output, dpi: int, ctx) -> None:
    """Save a figure while avoiding tight_layout warnings for complex axes."""
    output.parent.mkdir(parents=True, exist_ok=True)
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
        axis.grid(True)
        return None

    plate = transform or ccrs.PlateCarree()
    try:
        if global_map:
            axis.set_global()
        elif extent is not None:
            axis.set_extent(extent, crs=plate)
        axis.add_feature(cfeature.LAND, facecolor="0.96", edgecolor="none", zorder=0)
        axis.add_feature(cfeature.OCEAN, facecolor="white", edgecolor="none", zorder=0)
        axis.coastlines(resolution="110m", linewidth=0.75, color="#334155", zorder=5)
        axis.add_feature(cfeature.BORDERS, linewidth=0.35, edgecolor="#64748b", zorder=5)
        gridlines = axis.gridlines(
            draw_labels=True,
            linewidth=0.45,
            linestyle=":",
            color="#cbd5e1",
            alpha=0.85,
        )
        gridlines.top_labels = False
        gridlines.right_labels = False
    except Exception:
        axis.grid(True)
        return None
    return plate


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
    maximum = _robust_abs_limit([field[local] for field in display_fields], np)
    if maximum <= 0.0:
        maximum = 1.0

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
    fig.suptitle(f"Resposta espacial da B: {label} a um impulso em $T_u$ (DIRAC)", fontsize=17)
    norm = ctx.plt.Normalize(vmin=-maximum, vmax=maximum)
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
                cmap="coolwarm",
                transform=transform,
            )
            scatter_kwargs = {"transform": transform} if transform is not None else {}
            axis.scatter(
                [lon0],
                [lat0],
                marker="x",
                s=105,
                color=runner.FG,
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
                cmap="coolwarm",
                transform=None,
            )
            axis.scatter([0.0], [lat0], marker="x", s=105, color=runner.FG, linewidths=2.2, zorder=3)
            axis.set_xlabel("Longitude relativa ao impulso (°)")
            axis.set_xlim(-dlon, dlon)
            axis.set_ylim(lat0 - dlat, lat0 + dlat)
            axis.grid(True)

        axis.set_title("2D/superfície" if item is None else f"Nível {item}")

    axes[0].set_ylabel("Latitude (°)")
    if artist is not None:
        colorbar = fig.colorbar(artist, cax=colorbar_axis)
        colorbar.set_label(f"Resposta em {label}", labelpad=12)
    fig.text(
        0.01,
        0.035,
        f"Impulso: {lat0:.1f}°, {lon0:.1f}°",
        fontsize=8,
        color=runner.MUTED,
        ha="left",
        va="bottom",
    )
    _finish(fig, output, dpi, ctx)


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
    vmin, vmax, cmap = _global_limits_and_cmap(finite_values, np)
    norm = ctx.plt.Normalize(vmin=vmin, vmax=vmax)

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
        top=0.86,
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
        axis.grid(True)
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
    level_label = "2D/superfície" if level is None else f"nível {level}"
    axis.set_title(f"{product_name} — {label} — {level_label}")
    if not has_map:
        axis.set_xlabel("Longitude (°)")
        axis.set_ylabel("Latitude (°)")
    colorbar = fig.colorbar(artist, cax=colorbar_axis)
    colorbar.set_label(label)
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


def _global_limits_and_cmap(values, np):
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return -1.0, 1.0, "coolwarm"
    vmin = float(np.nanpercentile(finite, 2.0))
    vmax = float(np.nanpercentile(finite, 98.0))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        vmin = float(np.nanmin(finite))
        vmax = float(np.nanmax(finite))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        center = 0.0 if not np.isfinite(vmin) else vmin
        return center - 1.0, center + 1.0, "viridis"
    if vmin < 0.0 < vmax:
        amplitude = max(abs(vmin), abs(vmax))
        return -amplitude, amplitude, "coolwarm"
    return vmin, vmax, "viridis"


def _spatial_artist(axis, x, y, values, norm, ctx, *, cmap="coolwarm", transform=None):
    values = ctx.np.asarray(values, dtype=float)
    kwargs = {"transform": transform} if transform is not None else {}
    if len(values) >= 20:
        try:
            triangulation = ctx.mtri.Triangulation(x, y)
            return axis.tricontourf(
                triangulation,
                values,
                levels=CONTOUR_LEVELS,
                cmap=cmap,
                norm=norm,
                extend="both",
                **kwargs,
            )
        except (TypeError, ValueError, RuntimeError):
            pass
    return axis.scatter(x, y, c=values, s=8, cmap=cmap, norm=norm, linewidths=0, zorder=3, **kwargs)
