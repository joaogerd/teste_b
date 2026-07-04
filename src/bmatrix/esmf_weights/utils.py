"""Small pure utility functions used by the package."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Compute the SHA-256 digest of a file.

    Parameters
    ----------
    path
        Existing file to hash.

    Returns
    -------
    str
        Lowercase hexadecimal SHA-256 digest.

    Raises
    ------
    FileNotFoundError
        If `path` does not exist.
    OSError
        If the file cannot be read.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolution_tag(value: float) -> str:
    """Format a decimal resolution as a filename-safe identifier.

    Parameters
    ----------
    value
        Positive grid resolution in degrees.

    Returns
    -------
    str
        A deterministic tag such as ``"1p0"`` or ``"0p25"``.

    Examples
    --------
    >>> resolution_tag(0.25)
    '0p25'
    """
    text = f"{value:.12g}"
    if "." not in text:
        text += ".0"
    return text.replace(".", "p").replace("-", "m")
