from __future__ import annotations

from pathlib import Path

from ..shell import qsub, require_file, wait_for_pbs_job, write_text


def run_job(workspace: str | Path, wait: bool = False, poll_seconds: int = 30) -> str:
    run_dir = Path(workspace) / "UNBALANCE"
    require_file(run_dir / "qsub_unbalance.bash", "qsub_unbalance.bash")
    jobid = qsub("qsub_unbalance.bash", run_dir)
    write_text(run_dir / "job_id.txt", jobid + "\n")
    if wait:
        wait_for_pbs_job(jobid, poll_seconds=poll_seconds)
    return jobid

