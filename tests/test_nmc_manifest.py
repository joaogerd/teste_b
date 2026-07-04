from __future__ import annotations

from pathlib import Path

import pytest

from bmatrix.bflow_core.manifest import read_manifest as read_bflow_manifest
from bmatrix.nmc_core.checks import validate_manifest
from bmatrix.nmc_core.manifest import ManifestError


def _write_manifest(tmp_path: Path, count: int) -> Path:
    rows = ["valid_time\tf048\tf024"]
    for hour in range(count):
        f048 = tmp_path / f"f048_{hour}.nc"
        f024 = tmp_path / f"f024_{hour}.nc"
        f048.write_bytes(b"f48")
        f024.write_bytes(b"f24")
        rows.append(f"2026-06-22T{hour:02d}:00:00Z\t{f048}\t{f024}")
    manifest = tmp_path / "bflow-manifest.tsv"
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return manifest


def test_manifest_requires_four_complete_pairs_and_normalizes_iso_time(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, 4)

    report = validate_manifest(manifest)
    bflow_pairs = read_bflow_manifest(manifest)

    assert report["valid"] is True
    assert report["pair_count"] == 4
    assert bflow_pairs[0].valid_time == "2026-06-22_00:00:00"


def test_manifest_rejects_too_few_pairs(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, 3)

    with pytest.raises(ManifestError, match="requires at least 4"):
        validate_manifest(manifest)
