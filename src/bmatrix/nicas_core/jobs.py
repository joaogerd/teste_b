"""NICAS submission logic using stage manifests for variable discovery."""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..artifacts import read_manifest
from ..shell import qsub, wait_for_pbs_job, write_text
from .checks import check, home_failure_files, variable_errors


def _variables(workspace: str | Path) -> tuple[str, ...]:
    manifest = read_manifest(workspace, expected_stage="nicas")
    raw = manifest.metadata.get("variables", [])
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise RuntimeError("Manifesto NICAS não contém a lista de variáveis.")
    return tuple(raw)


def qsub_afterok(pbs_file: str, cwd: Path, jobids: list[str]) -> str:
    """Submit a PBS job dependent on successful completion of all predecessors."""
    dependency = ":".join(jobids)
    command = ["qsub", "-W", f"depend=afterok:{dependency}", pbs_file]
    process = subprocess.run(command, cwd=cwd, check=False, text=True, capture_output=True)
    if process.returncode != 0:
        raise RuntimeError(f"qsub do merge NICAS falhou: {process.stderr.strip()}")
    return process.stdout.strip().split()[0]


def clean_variable_outputs(run_dir: Path) -> None:
    """Remove only reproducible per-variable NICAS outputs."""
    for name in ("run_nicas.runlog", "stdout.log", "stderr.log", "mpas_nicas.nc", "mpas.nicas_norm.nc", "mpas.dirac_nicas.nc"):
        (run_dir / name).unlink(missing_ok=True)
    for pattern in ("mpas_nicas_local_*", "mpas_nicas_grids_local_*"):
        for path in run_dir.glob(pattern):
            path.unlink()


def run_variable(variable: str, run_dir: Path, retries: int, poll_seconds: int) -> str:
    """Submit and validate a single NICAS-variable job with retry support."""
    for attempt in range(retries + 1):
        clean_variable_outputs(run_dir)
        for path in home_failure_files(run_dir):
            path.unlink()
        jobid = qsub("qsub_nicas.bash", run_dir)
        write_text(run_dir / "job_id.txt", jobid + "\n")
        wait_for_pbs_job(jobid, poll_seconds=poll_seconds)
        if home_failure_files(run_dir):
            if attempt < retries:
                continue
            raise RuntimeError(f"Falha PBS/HOME persistiu para NICAS {variable}.")
        errors = variable_errors(run_dir)
        if not errors:
            return jobid
        raise RuntimeError(f"NICAS falhou para {variable}: " + "; ".join(errors))
    raise AssertionError("Loop NICAS terminou inesperadamente.")


def run_job(
    workspace: str | Path,
    wait: bool = False,
    poll_seconds: int = 30,
    parallel: bool = False,
    retries: int = 2,
) -> str:
    """Submit the NICAS split/merge sequence."""
    root = Path(workspace)
    merge_dir = root / "merge"
    variables = _variables(root)
    retries = max(0, retries)
    if parallel:
        jobids = []
        for variable in variables:
            run_dir = root / variable
            jobid = qsub("qsub_nicas.bash", run_dir)
            write_text(run_dir / "job_id.txt", jobid + "\n")
            jobids.append(jobid)
        merge_jobid = qsub_afterok("qsub_nicas_merge.bash", merge_dir, jobids)
    else:
        for variable in variables:
            run_variable(variable, root / variable, retries=retries, poll_seconds=poll_seconds)
        merge_jobid = qsub("qsub_nicas_merge.bash", merge_dir)
    write_text(merge_dir / "job_id.txt", merge_jobid + "\n")
    if wait:
        wait_for_pbs_job(merge_jobid, poll_seconds=poll_seconds)
        check(root)
    return merge_jobid
