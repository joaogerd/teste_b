from __future__ import annotations

from pathlib import Path

import xarray as xr

from .statistics import VariableStats, compare_variable


def _selected_variables(old: xr.Dataset, new: xr.Dataset, variables: list[str] | None) -> list[str]:
    if variables:
        return list(dict.fromkeys(variables))
    names = sorted(set(old.data_vars) | set(new.data_vars))
    return names


def compare_datasets(
    old_path: str | Path,
    new_path: str | Path,
    variables: list[str] | None = None,
) -> list[VariableStats]:
    old_path = Path(old_path)
    new_path = Path(new_path)
    if not old_path.exists():
        raise SystemExit(f"ERRO: arquivo antigo não encontrado: {old_path}")
    if not new_path.exists():
        raise SystemExit(f"ERRO: arquivo novo não encontrado: {new_path}")

    with xr.open_dataset(old_path) as old, xr.open_dataset(new_path) as new:
        names = _selected_variables(old, new, variables)
        return [compare_variable(name, old, new) for name in names]


def write_diff_dataset(
    old_path: str | Path,
    new_path: str | Path,
    out_path: str | Path,
    variables: list[str] | None = None,
) -> Path:
    old_path = Path(old_path)
    new_path = Path(new_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with xr.open_dataset(old_path) as old, xr.open_dataset(new_path) as new:
        names = _selected_variables(old, new, variables)
        diff_vars = {}
        for name in names:
            if name not in old or name not in new:
                continue
            if old[name].shape != new[name].shape:
                continue
            if old[name].dtype.kind not in "iufc" or new[name].dtype.kind not in "iufc":
                continue
            diff_vars[name] = new[name] - old[name]
        if not diff_vars:
            raise SystemExit("ERRO: nenhuma variável numérica compatível para gravar diff.")
        diff = xr.Dataset(diff_vars)
        diff.attrs["comparison"] = "new_minus_old"
        diff.attrs["old_file"] = str(old_path)
        diff.attrs["new_file"] = str(new_path)
        diff.to_netcdf(out_path)
    return out_path
