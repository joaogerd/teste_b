"""Small, observable shell and PBS helpers used by B-matrix stages."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time


_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_ANSI = {
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "dim": "\033[2m",
    "reset": "\033[0m",
}
_PBS_STATES = frozenset({"B", "E", "F", "H", "M", "Q", "R", "S", "T", "W", "X"})


def _color_enabled() -> bool:
    """Return whether terminal output should contain ANSI color sequences.

    ``MPAS_BMATRIX_COLOR`` accepts ``always``, ``never`` and ``auto``. The
    default is ``auto``; colors are emitted only in an interactive terminal.
    ``NO_COLOR`` always disables color as specified by no-color.org.
    """
    if os.environ.get("NO_COLOR") is not None:
        return False
    mode = os.environ.get("MPAS_BMATRIX_COLOR", "auto").strip().lower()
    if mode == "always":
        return True
    if mode == "never":
        return False
    return sys.stdout.isatty()


def _paint(text: str, color: str) -> str:
    """Apply one optional ANSI foreground color to ``text``."""
    if not _color_enabled():
        return text
    return f"{_ANSI[color]}{text}{_ANSI['reset']}"


def _format_elapsed(seconds: float) -> str:
    """Format a monotonic elapsed duration as ``MM:SS`` or ``HH:MM:SS``."""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _pbs_state(status: str) -> str:
    """Extract a compact PBS state from a ``qstat`` row when possible."""
    for token in reversed(status.replace("|", " ").split()):
        if token in _PBS_STATES:
            return token
    return status


def _spinner_line(jobid: str, state: str, elapsed: str, remaining: float, frame: str) -> str:
    """Build one concise interactive PBS waiting line."""
    next_check = max(0, int(remaining))
    return (
        f"{_paint(frame, 'cyan')} "
        f"PBS job {jobid}: state {_paint(state, 'yellow')} "
        f"{_paint(f'elapsed {elapsed}', 'dim')} "
        f"{_paint(f'next check in {next_check}s', 'dim')}"
    )


def _erase_spinner_line() -> None:
    """Clear the current terminal row used by the interactive spinner."""
    sys.stdout.write("\r\033[2K")
    sys.stdout.flush()


def run(cmd, cwd=None, check=True):
    """Run one local command while echoing its argv for provenance."""
    print(_paint("+", "cyan"), " ".join(map(str, cmd)), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=check)


def write_text(path, text):
    """Write UTF-8 text, creating the parent directory when required."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def symlink_force(src, dst):
    """Create or replace one symbolic link."""
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    dst.symlink_to(src)


def require_file(path, label=None):
    """Return an existing path or stop with a domain-oriented error message."""
    path = Path(path)
    if not path.exists():
        msg = f"ERRO: arquivo obrigatório não encontrado: {path}"
        if label:
            msg = f"ERRO: {label} não encontrado: {path}"
        raise SystemExit(msg)
    return path


def qsub(pbs_file, cwd, block: bool = False):
    """Submit a PBS file and return its scheduler job identifier."""
    cmd = ["qsub"]
    if block:
        cmd.extend(["-W", "block=true"])
    cmd.append(str(pbs_file))
    cwd = Path(cwd)
    print(_paint("•", "cyan"), f"PBS: submitting {pbs_file}", flush=True)
    start = time.monotonic()
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    out = proc.stdout.strip()
    err = proc.stderr.strip()
    elapsed = _format_elapsed(time.monotonic() - start)

    if proc.returncode != 0:
        msg = [
            f"ERRO: qsub falhou com código {proc.returncode}",
            f"cwd={cwd}",
            f"pbs_file={pbs_file}",
            f"block={block}",
        ]
        if out:
            msg.append(f"STDOUT:\n{out}")
        if err:
            msg.append(f"STDERR:\n{err}")
        raise SystemExit("\n".join(msg))

    jobid = out.split()[0] if out else ""
    if not jobid:
        raise SystemExit("ERRO: qsub não retornou um identificador de job PBS.")
    print(_paint("✓", "green"), f"PBS: submitted {pbs_file} as {jobid} {_paint(f'({elapsed})', 'dim')}", flush=True)
    if err:
        print(_paint("!", "yellow"), err, flush=True)
    return jobid


def pbs_job_status(jobid: str) -> str | None:
    """Return the final non-empty ``qstat`` row, or ``None`` when absent."""
    if not jobid:
        return None
    proc = subprocess.run(
        ["qstat", jobid],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if proc.returncode != 0:
        return None

    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if len(lines) >= 3:
        return lines[-1].strip()
    return proc.stdout.strip() or None


def pbs_job_exists(jobid: str) -> bool:
    """Return whether the PBS scheduler currently lists the job."""
    return pbs_job_status(jobid) is not None


def wait_for_pbs_job(jobid: str, poll_seconds: int = 30):
    """Wait for a PBS job with a colored braille spinner when interactive.

    The scheduler is queried only once per ``poll_seconds`` interval. Between
    queries, an in-place braille spinner keeps the terminal visibly alive.
    When output is redirected, persistent ``[RUN]`` lines are printed instead
    so log files remain readable and do not contain ANSI control sequences.

    Parameters
    ----------
    jobid : str
        Job identifier returned by ``qsub``.
    poll_seconds : int, default=30
        Minimum interval between ``qstat`` calls.
    """
    if not jobid:
        raise SystemExit("ERRO: jobid vazio; não é possível monitorar o PBS.")

    poll_seconds = max(1, int(poll_seconds))
    interactive = sys.stdout.isatty()
    start = time.monotonic()
    next_poll = start
    status = "checking scheduler"
    frame_index = 0

    if not interactive:
        print(_paint("•", "cyan"), f"PBS job {jobid}: waiting for completion.", flush=True)

    while True:
        now = time.monotonic()
        if now >= next_poll:
            observed = pbs_job_status(jobid)
            elapsed = _format_elapsed(now - start)
            if observed is None:
                if interactive:
                    _erase_spinner_line()
                print(
                    _paint("✓", "green"),
                    f"PBS job {jobid}: no longer listed; validating outputs {_paint(f'({elapsed})', 'dim')}",
                    flush=True,
                )
                return

            status = _pbs_state(observed)
            next_poll = now + poll_seconds
            if not interactive:
                print(
                    _paint("[RUN]", "cyan"),
                    f"PBS job {jobid}: state {status}; elapsed {elapsed}; next check in {poll_seconds}s.",
                    flush=True,
                )

        if interactive:
            elapsed = _format_elapsed(time.monotonic() - start)
            remaining = next_poll - time.monotonic()
            line = _spinner_line(jobid, status, elapsed, remaining, _SPINNER_FRAMES[frame_index])
            sys.stdout.write("\r\033[2K" + line)
            sys.stdout.flush()
            frame_index = (frame_index + 1) % len(_SPINNER_FRAMES)

        sleep_for = min(0.1, max(0.01, next_poll - time.monotonic())) if interactive else max(0.01, next_poll - time.monotonic())
        time.sleep(sleep_for)
