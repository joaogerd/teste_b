"""Read and write the BFLOW input contract."""
from __future__ import annotations

import csv
from pathlib import Path

from ..nmc_core.manifest import read_manifest as read_nmc_manifest
from .model import BflowPair


def read_manifest(path: str | Path) -> list[BflowPair]:
    """Read producer manifests, accepting ISO-8601 or MPAS valid-time values."""
    return [
        BflowPair(pair.valid_time, pair.f048, pair.f024)
        for pair in read_nmc_manifest(path)
    ]


def write_manifest(path: str | Path, pairs: list[BflowPair]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["valid_time", "f048", "f024"], delimiter="\t")
        writer.writeheader()
        for pair in pairs:
            writer.writerow({"valid_time": pair.valid_time, "f048": str(pair.f048), "f024": str(pair.f024)})
    return path
