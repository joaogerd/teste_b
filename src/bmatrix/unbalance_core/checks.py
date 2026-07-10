from __future__ import annotations

import math
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Iterable

import netCDF4
import numpy as np

from ..artifacts import read_manifest, write_manifest
from ..scientific_config import ordered_control_file_names


def _manifest_value(workspace: Path, key: str) -> str:
    manifest = read_manifest(workspace, expected_stage="unbalance")
    value = manifest.metadata.get(key)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Manifesto UNBALANCE não contém {key}.")
    return value


def _expected_members(stem: str, nmembers: int) -> list[str]:
    return [f"{stem}_{index:03d}.nc" for index in range(1, nmembers + 1)]


def _ncdump_kind(path: Path) -> str:
    proc = subprocess.run(["ncdump", "-k", str(path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ncdump -k falhou para {path}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _has_nan(values: np.ndarray) -> bool:
    if not np.issubdtype(values.dtype, np.floating):
        return False
    return bool(np.isnan(values).any())


def _expected_xtime(value: str | None) -> str | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d_%H:%M:%S")


def _decode_xtime(value: np.ndarray) -> str:
    row = np.asarray(value)
    if row.ndim > 1:
        row = row[0]
    if row.dtype.kind in {"S", "U"}:
        return "".join(item.decode() if isinstance(item, bytes) else str(item) for item in row).strip()
    return "".join(chr(int(item)) for item in row).strip()


def validate_unbalanced_samples(
    workspace: str | Path,
    *,
    required_variables: Iterable[str],
    expected_date: str | None = None,
    expected_stream: str = "control",
    expected_members: int = 4,
) -> list[str]:
    """Return structural and numerical errors for UNBALANCE outputs."""
    root = Path(workspace)
    stem = _manifest_value(root, "sample_stem")
    sample_dir = root / "samplesUnbalanced"
    expected_names = _expected_members(stem, expected_members)
    expected_xtime = _expected_xtime(expected_date)
    found = sorted(path.name for path in sample_dir.glob(f"{stem}_*.nc"))
    errors: list[str] = []
    if found != expected_names:
        errors.append(
            "amostras UNBALANCE inválidas: "
            f"esperadas={expected_names}, encontradas={found}"
        )
        return errors

    for name in expected_names:
        path = sample_dir / name
        if path.stat().st_size <= 0:
            errors.append(f"arquivo vazio: {path}")
            continue
        try:
            kind = _ncdump_kind(path)
        except RuntimeError as exc:
            errors.append(str(exc))
            continue
        if kind != "cdf5":
            errors.append(f"formato NetCDF inválido em {path.name}: esperado cdf5, obtido {kind}")
            continue
        try:
            with netCDF4.Dataset(path) as dataset:
                for variable in required_variables:
                    if variable not in dataset.variables:
                        errors.append(f"variável ausente em {path.name}: {variable}")
                        continue
                    data = dataset.variables[variable][:]
                    if _has_nan(np.asarray(data)):
                        errors.append(f"NaN detectado em {path.name}:{variable}")
                xtime = dataset.variables.get("xtime")
                if expected_date and xtime is not None:
                    raw = np.asarray(xtime[:])
                    if raw.size == 0 or not math.isfinite(float(raw.size)):
                        errors.append(f"xtime inválido em {path.name}")
                    elif expected_xtime and _decode_xtime(raw) != expected_xtime:
                        errors.append(
                            f"data incompatível em {path.name}: "
                            f"esperada {expected_xtime}, obtida {_decode_xtime(raw)}"
                        )
                stream = getattr(dataset, "stream", expected_stream)
                if stream != expected_stream:
                    errors.append(f"stream incompatível em {path.name}: esperado {expected_stream}, obtido {stream}")
        except OSError as exc:
            errors.append(f"NetCDF inválido em {path.name}: {exc}")
    return errors


def check(workspace: str | Path, config: dict | None = None) -> bool:
    root = Path(workspace)
    run_dir = root / "UNBALANCE"
    manifest = read_manifest(root, expected_stage="unbalance")
    text = (run_dir / "run_unbalance.runlog").read_text(errors="replace") if (run_dir / "run_unbalance.runlog").is_file() else ""
    errors: list[str] = []
    if not (run_dir / "run_unbalance.runlog").is_file():
        errors.append("run_unbalance.runlog ausente")
    if "Finishing oops::UnbalanceEnsemble<MPAS> with status = 0" not in text and "with status = 0" not in text:
        errors.append("status final de sucesso ausente no run_unbalance.runlog")
    if config is not None:
        variables = ordered_control_file_names(config, config.get("vbal", {}).get("group_variable_order"))
    else:
        variables = ("stream_function", "velocity_potential", "temperature", "spechum", "surface_pressure")
    members = int(manifest.metadata.get("members", 4))
    errors.extend(
        validate_unbalanced_samples(
            root,
            required_variables=variables,
            expected_date=str(manifest.metadata.get("date", "")),
            expected_members=members,
        )
    )

    print("=== UNBALANCE validation ===")
    print(f"WORKSPACE={root}")
    if errors:
        for error in errors:
            print(f"  - {error}")
        print_diagnostics(root)
        raise RuntimeError("UNBALANCE falhou ou ficou incompleto.")

    write_manifest(
        type(manifest)(
            stage=manifest.stage,
            workspace=manifest.workspace,
            inputs=manifest.inputs,
            outputs=manifest.outputs,
            metadata=manifest.metadata,
            status="completed",
            schema_version=manifest.schema_version,
            created_at_utc=manifest.created_at_utc,
        )
    )
    print("SUCCESS: UNBALANCE validado.")
    return True


def print_diagnostics(workspace: Path, tail_lines: int = 80) -> None:
    run_dir = workspace / "UNBALANCE"
    print("=== UNBALANCE diagnostics ===")
    for name in ["stdout.log", "stderr.log", "run_unbalance.runlog", "log.atmosphere.0000.err"]:
        path = run_dir / name
        print(f"--- {path} (ultimas {tail_lines} linhas) ---")
        if not path.is_file():
            print("[arquivo ausente]")
            continue
        lines = path.read_text(errors="replace").splitlines()
        print("\n".join(lines[-tail_lines:]) or "[arquivo vazio]")
