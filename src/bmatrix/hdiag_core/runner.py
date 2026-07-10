from __future__ import annotations

from .checks import check
from .jobs import run_job

submit = run_job
validate = check
