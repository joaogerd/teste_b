from __future__ import annotations

from pathlib import Path
import subprocess
import time


def run(cmd, cwd=None, check=True):
    print("+", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=check)


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def symlink_force(src, dst):
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    dst.symlink_to(src)


def require_file(path, label=None):
    path = Path(path)
    if not path.exists():
        msg = f"ERRO: arquivo obrigatório não encontrado: {path}"
        if label:
            msg = f"ERRO: {label} não encontrado: {path}"
        raise SystemExit(msg)
    return path


def qsub(pbs_file, cwd, block: bool = False):
    cmd = ["qsub"]
    if block:
        cmd.extend(["-W", "block=true"])
    cmd.append(str(pbs_file))
    cwd = Path(cwd)
    print("+", " ".join(map(str, cmd)), flush=True)
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

    if out:
        print(out, flush=True)
    if err:
        print(err, flush=True)

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

    return out.split()[0] if out else ""


def pbs_job_status(jobid: str) -> str | None:
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
    return pbs_job_status(jobid) is not None


def _format_elapsed(seconds: float) -> str:
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def wait_for_pbs_job(jobid: str, poll_seconds: int = 30):
    if not jobid:
        raise SystemExit("ERRO: jobid vazio; não é possível monitorar o PBS.")

    poll_seconds = max(1, int(poll_seconds))
    start = time.monotonic()
    print(f"Aguardando job PBS terminar: {jobid}", flush=True)

    while True:
        status = pbs_job_status(jobid)
        if status is None:
            break

        elapsed = _format_elapsed(time.monotonic() - start)
        print(f"Ainda aguardando PBS job {jobid} | elapsed={elapsed} | {status}", flush=True)
        time.sleep(poll_seconds)

    elapsed = _format_elapsed(time.monotonic() - start)
    print(f"Job PBS saiu do qstat: {jobid} | elapsed={elapsed}", flush=True)
