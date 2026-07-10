"""Left-aligned title layout for B-matrix diagnostic figures.

The plotting stage already centralizes palette, map background and typography in
``map_enhancements``. This module applies one final presentation rule: figure
and single-panel titles should be aligned with the left edge of the plotting
area and placed close to the axes, following the style used in the user's
reference academic figures.
"""
from __future__ import annotations


MAIN_TITLE_SIZE = 15.5
AXIS_TITLE_SIZE = 13.0
TITLE_PAD = 7
TITLE_GAP = 0.025
TITLE_MAX_Y = 0.965
TITLE_FALLBACK_X = 0.08
DATA_AXIS_MIN_WIDTH = 0.12
DATA_AXIS_MIN_HEIGHT = 0.12


def apply() -> None:
    """Patch all active finish helpers to align titles at save time."""
    from . import map_enhancements
    from . import runner

    _patch_finish(runner, "_finish")
    _patch_finish(map_enhancements, "_finish")


def _patch_finish(module, name: str) -> None:
    previous_finish = getattr(module, name)
    if getattr(previous_finish, "_bmatrix_left_title_layout", False):
        return

    def _finish(fig, output, dpi: int, ctx):
        _apply_title_layout(fig)
        return previous_finish(fig, output, dpi, ctx)

    _finish._bmatrix_left_title_layout = True  # type: ignore[attr-defined]
    setattr(module, name, _finish)


def _apply_title_layout(fig) -> None:
    data_axes = _data_axes(fig)
    _align_figure_title(fig, data_axes)
    _align_single_axis_titles(fig, data_axes)


def _data_axes(fig) -> list:
    axes = []
    for axis in fig.get_axes():
        box = axis.get_position()
        if box.width < DATA_AXIS_MIN_WIDTH or box.height < DATA_AXIS_MIN_HEIGHT:
            continue
        axes.append(axis)
    return axes


def _align_figure_title(fig, data_axes: list) -> None:
    title = getattr(fig, "_suptitle", None)
    if title is None:
        return

    if data_axes:
        x0 = min(axis.get_position().x0 for axis in data_axes)
        y1 = max(axis.get_position().y1 for axis in data_axes)
    else:
        x0 = TITLE_FALLBACK_X
        y1 = 0.90

    title.set_x(float(x0))
    title.set_y(float(min(TITLE_MAX_Y, y1 + TITLE_GAP)))
    title.set_ha("left")
    title.set_va("bottom")
    title.set_fontsize(MAIN_TITLE_SIZE)
    title.set_fontweight("bold")


def _align_single_axis_titles(fig, data_axes: list) -> None:
    """Move standalone axes titles to the left edge.

    When a figure has a suptitle, axes titles are usually panel labels such as
    ``Nível 25`` and should remain centered. Without a suptitle, the axes title
    is the main figure title and should follow the left-aligned academic style.
    """
    if getattr(fig, "_suptitle", None) is not None:
        return

    for axis in data_axes:
        title = axis.get_title()
        if not title:
            continue
        axis.set_title("")
        axis.set_title(
            title,
            loc="left",
            pad=TITLE_PAD,
            fontsize=AXIS_TITLE_SIZE,
            fontweight="bold",
        )
