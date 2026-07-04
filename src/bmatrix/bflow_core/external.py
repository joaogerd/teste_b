from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable


def run_shell(command: str, cwd: Path, log_path: Path | None = None, env: dict[str, str] | None = None) -> None:
    cwd = Path(cwd)
    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    log_file = None
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("a")
        log_file.write(f"\n$ {command}\n")
        log_file.flush()

    try:
        proc = subprocess.Popen(
            ["bash", "-lc", command],
            cwd=cwd,
            env=run_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            if log_file is not None:
                log_file.write(line)
        rc = proc.wait()
        if rc != 0:
            raise SystemExit(f"ERRO: comando falhou com código {rc}: {command}")
    finally:
        if log_file is not None:
            log_file.close()


def require_files(paths: Iterable[Path], label: str) -> None:
    missing = [str(p) for p in paths if not Path(p).exists()]
    if missing:
        raise SystemExit(f"ERRO: arquivos ausentes em {label}:\n" + "\n".join(missing))
