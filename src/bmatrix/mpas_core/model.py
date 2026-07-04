from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from ..config import safe_time


DA_STATE_REQUIRED_VARIABLES = [
    "uReconstructZonal",
    "uReconstructMeridional",
    "theta",
    "pressure_p",
    "pressure_base",
    "qv",
    "surface_pressure",
    "qc",
    "qr",
    "qi",
    "qs",
    "qg",
]


def parse_time(t: str) -> datetime:
    return datetime.strptime(t, "%Y-%m-%d_%H:%M:%S")


def fmt_file_time(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d_%H.%M.%S")


def forecast_run_dir(config, init_time: str, lead_hours: int, dt: int) -> Path:
    mesh = config["mesh"]["name"]
    nproc = int(config["mesh"].get("nproc", 64))
    return (
        Path(config["project"]["work_root"])
        / "runs"
        / f"forecast_{mesh}_{safe_time(init_time)}_f{lead_hours:03d}_dt{dt}_np{nproc}"
    )


def restart_file(config, init_time: str, lead_hours: int, dt: int) -> Path:
    valid = parse_time(init_time) + timedelta(hours=lead_hours)
    return forecast_run_dir(config, init_time, lead_hours, dt) / f"restart.{fmt_file_time(valid)}.nc"


def bflow_file(config, init_time: str, lead_hours: int, dt: int) -> Path:
    """Return the MPAS-JEDI da_state file used by BFLOW."""
    valid = parse_time(init_time) + timedelta(hours=lead_hours)
    return forecast_run_dir(config, init_time, lead_hours, dt) / f"mpasout.{fmt_file_time(valid)}.nc"
