from __future__ import annotations

from .jobs import run_job
from .prepare import prepare
from .validate import validate

submit = run_job

__all__ = ["prepare", "run_job", "submit", "validate"]
