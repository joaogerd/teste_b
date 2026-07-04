"""Read the minimal producer/consumer contract used by BFLOW."""
from __future__ import annotations

import csv
from pathlib import Path

from .model import NMCManifestPair, normalize_time


class ManifestError(ValueError):
    """The tab-separated NMC producer manifest is invalid."""


def read_manifest(path: str | Path) -> list[NMCManifestPair]:
    """Read ``valid_time, f048, f024`` rows and normalize valid times."""
    path = Path(path)
    if not path.is_file():
        raise ManifestError(f"NMC manifest does not exist: {path}")
    pairs: list[NMCManifestPair] = []
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        required = {"valid_time", "f048", "f024"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ManifestError(
                f"NMC manifest {path} must have tab-separated columns: valid_time, f048, f024."
            )
        for index, row in enumerate(reader, start=2):
            raw_valid = (row.get("valid_time") or "").strip()
            raw_f048 = (row.get("f048") or "").strip()
            raw_f024 = (row.get("f024") or "").strip()
            if not raw_f048 or not raw_f024:
                raise ManifestError(f"NMC manifest {path}:{index} has an empty f048 or f024 path.")
            try:
                valid_time = normalize_time(raw_valid)
            except ValueError as error:
                raise ManifestError(f"Invalid valid_time at {path}:{index}: {error}") from error
            pairs.append(NMCManifestPair(valid_time, Path(raw_f048), Path(raw_f024)))
    if not pairs:
        raise ManifestError(f"NMC manifest has no pair rows: {path}")
    return pairs
