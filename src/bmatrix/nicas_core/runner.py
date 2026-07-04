from __future__ import annotations

from .checks import check
from .jobs import run_job
from .prepare import prepare

submit = run_job
validate = check
