from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import xarray as xr


@dataclass(frozen=True)
class VariableStats:
    name: str
    status: str
    shape_old: tuple[int, ...] | None = None
    shape_new: tuple[int, ...] | None = None
    count: int = 0
    bias: float | None = None
    mae: float | None = None
    rmse: float | None = None
    rel_rmse: float | None = None
    max_abs: float | None = None
    std_old: float | None = None
    std_new: float | None = None
    corr: float | None = None
    note: str = ""


def _finite_pair(old: xr.DataArray, new: xr.DataArray) -> tuple[np.ndarray, np.ndarray]:
    old_values = np.asarray(old.values, dtype="f8").ravel()
    new_values = np.asarray(new.values, dtype="f8").ravel()
    mask = np.isfinite(old_values) & np.isfinite(new_values)
    return old_values[mask], new_values[mask]


def _safe_corr(old: np.ndarray, new: np.ndarray) -> float | None:
    if old.size < 2:
        return None
    old_std = float(np.std(old))
    new_std = float(np.std(new))
    if old_std == 0.0 or new_std == 0.0:
        if np.allclose(old, new, equal_nan=True):
            return 1.0
        return None
    return float(np.corrcoef(old, new)[0, 1])


def _relative_rmse(rmse: float, std_old: float) -> float | None:
    if std_old == 0.0:
        return 0.0 if rmse == 0.0 else None
    return float(rmse / std_old)


def compare_variable(name: str, old: xr.Dataset, new: xr.Dataset) -> VariableStats:
    if name not in old:
        return VariableStats(name=name, status="missing_old", note="variável ausente no arquivo antigo")
    if name not in new:
        return VariableStats(name=name, status="missing_new", note="variável ausente no arquivo novo")

    old_var = old[name]
    new_var = new[name]
    if old_var.shape != new_var.shape:
        return VariableStats(
            name=name,
            status="shape_mismatch",
            shape_old=tuple(old_var.shape),
            shape_new=tuple(new_var.shape),
            note="shapes diferentes; estatísticas não calculadas",
        )

    if not np.issubdtype(old_var.dtype, np.number) or not np.issubdtype(new_var.dtype, np.number):
        return VariableStats(
            name=name,
            status="non_numeric",
            shape_old=tuple(old_var.shape),
            shape_new=tuple(new_var.shape),
            note="variável não numérica ignorada",
        )

    old_values, new_values = _finite_pair(old_var, new_var)
    if old_values.size == 0:
        return VariableStats(
            name=name,
            status="no_finite_values",
            shape_old=tuple(old_var.shape),
            shape_new=tuple(new_var.shape),
            note="sem pares finitos para comparar",
        )

    diff = new_values - old_values
    rmse = float(np.sqrt(np.mean(diff * diff)))
    std_old = float(np.std(old_values))
    return VariableStats(
        name=name,
        status="ok",
        shape_old=tuple(old_var.shape),
        shape_new=tuple(new_var.shape),
        count=int(diff.size),
        bias=float(np.mean(diff)),
        mae=float(np.mean(np.abs(diff))),
        rmse=rmse,
        rel_rmse=_relative_rmse(rmse, std_old),
        max_abs=float(np.max(np.abs(diff))),
        std_old=std_old,
        std_new=float(np.std(new_values)),
        corr=_safe_corr(old_values, new_values),
    )


def format_number(value: float | None) -> str:
    if value is None:
        return "-"
    if not np.isfinite(value):
        return "nan"
    if value == 0.0:
        return "0"
    abs_value = abs(value)
    if abs_value >= 1.0e4 or abs_value < 1.0e-3:
        return f"{value:.4e}"
    return f"{value:.6g}"
