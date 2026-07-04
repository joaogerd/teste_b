"""Minimal MPAS path conventions consumed by the B-matrix workflow.

Forecast and initialization orchestration intentionally live outside this
package.  The B-matrix pipeline only needs deterministic paths to existing
``da_state`` products.
"""

from .model import bflow_file, forecast_run_dir, restart_file

__all__ = ["bflow_file", "forecast_run_dir", "restart_file"]
