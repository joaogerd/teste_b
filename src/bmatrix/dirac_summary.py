from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np


def _numeric_variables(dataset):
    for name, variable in dataset.variables.items():
        if getattr(variable, "dimensions", None) is None:
            continue
        if not np.issubdtype(np.dtype(variable.dtype), np.number):
            continue
        yield name, variable


def summarize_dirac_file(path: str | Path) -> list[dict[str, object]]:
    """Return lightweight statistics for numeric variables in a Dirac NetCDF file."""
    result: list[dict[str, object]] = []
    from netCDF4 import Dataset
    with Dataset(path) as dataset:
        for name, variable in _numeric_variables(dataset):
            values = np.ma.asarray(variable[:])
            if values.size == 0:
                result.append(
                    {
                        "variable": name,
                        "shape": tuple(variable.shape),
                        "min": None,
                        "max": None,
                        "rms": None,
                        "absmax": None,
                        "nonzero": False,
                    }
                )
                continue
            compressed = values.compressed() if np.ma.isMaskedArray(values) else np.asarray(values).ravel()
            if compressed.size == 0:
                nonzero = False
                vmin = vmax = rms = absmax = math.nan
            else:
                arr = np.asarray(compressed, dtype=float)
                nonzero = bool(np.any(arr != 0.0))
                vmin = float(np.min(arr))
                vmax = float(np.max(arr))
                rms = float(np.sqrt(np.mean(arr * arr)))
                absmax = float(np.max(np.abs(arr)))
            result.append(
                {
                    "variable": name,
                    "shape": tuple(variable.shape),
                    "min": vmin,
                    "max": vmax,
                    "rms": rms,
                    "absmax": absmax,
                    "nonzero": nonzero,
                }
            )
    return result


def print_summary(rows: list[dict[str, object]]) -> None:
    print("variable,shape,min,max,rms,absmax,nonzero")
    for row in rows:
        shape = "x".join(str(value) for value in row["shape"])
        print(
            f"{row['variable']},{shape},{row['min']},{row['max']},{row['rms']},{row['absmax']},{row['nonzero']}"
        )


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mpasdirac-summary",
        description="Resume variaveis numericas de um arquivo mpas.dirac.nc",
    )
    p.add_argument("path", help="Arquivo mpas.dirac.nc")
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    path = Path(args.path)
    if not path.is_file():
        raise SystemExit(f"ERRO: arquivo nao encontrado: {path}")
    print_summary(summarize_dirac_file(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
