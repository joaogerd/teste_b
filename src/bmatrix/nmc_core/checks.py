"""Completeness checks for NMC manifests consumed by BFLOW."""
from __future__ import annotations

from pathlib import Path

from .manifest import ManifestError, read_manifest
from .model import MINIMUM_PAIRS, NMCManifestPair, parse_time


def _require_product(path: Path, label: str) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size == 0:
        raise ManifestError(f"Required {label} product is missing or empty: {path}")
    return {"path": str(path.resolve()), "bytes": path.stat().st_size}


def validate_pairs(pairs: list[NMCManifestPair], *, minimum_pairs: int = MINIMUM_PAIRS) -> dict[str, object]:
    """Validate chronology, uniqueness and product availability for NMC inputs."""
    if minimum_pairs < MINIMUM_PAIRS:
        raise ManifestError(
            f"minimum_pairs cannot be below {MINIMUM_PAIRS}; fewer samples are only suitable for isolated code tests."
        )
    if len(pairs) < minimum_pairs:
        raise ManifestError(
            f"NMC manifest contains {len(pairs)} pair(s), but B-matrix calibration requires at least {minimum_pairs}."
        )

    previous = None
    seen: set[str] = set()
    records = []
    for pair in pairs:
        parsed = parse_time(pair.valid_time)
        if pair.valid_time in seen:
            raise ManifestError(f"Duplicate NMC valid_time: {pair.valid_time}")
        if previous is not None and parsed <= previous:
            raise ManifestError("NMC manifest valid_time values must be strictly increasing.")
        if pair.f048.resolve() == pair.f024.resolve():
            raise ManifestError(f"f048 and f024 resolve to the same file for {pair.valid_time}.")
        records.append(
            {
                "valid_time": pair.valid_time,
                "f048": _require_product(pair.f048, f"f048 for {pair.valid_time}"),
                "f024": _require_product(pair.f024, f"f024 for {pair.valid_time}"),
            }
        )
        seen.add(pair.valid_time)
        previous = parsed
    return {"valid": True, "minimum_pairs": minimum_pairs, "pairs": records}


def validate_manifest(path: str | Path, *, minimum_pairs: int = MINIMUM_PAIRS) -> dict[str, object]:
    """Read and validate a producer manifest consumed by the unified B-matrix workflow."""
    pairs = read_manifest(path)
    report = validate_pairs(pairs, minimum_pairs=minimum_pairs)
    report["manifest"] = str(Path(path).resolve())
    report["pair_count"] = len(pairs)
    return report
