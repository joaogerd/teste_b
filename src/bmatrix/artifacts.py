"""Persistent, machine-readable stage manifests.

README files remain useful for people, but downstream workflow stages use this
module instead of parsing prose to find their inputs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Mapping

from .errors import ArtifactError

MANIFEST_NAME = "stage-manifest.json"


@dataclass(frozen=True, slots=True)
class StageManifest:
    """Provenance and artifact contract for a completed or prepared stage.

    Parameters
    ----------
    stage
        Canonical stage identifier, such as ``"vbal"`` or ``"nicas"``.
    workspace
        Root directory owned by the stage.
    inputs
        Named input artifacts or upstream workspaces.
    outputs
        Named output artifacts.  A path may be planned before the stage runs.
    metadata
        Small JSON-serializable details such as member count or variant.
    status
        One of ``"planned"``, ``"prepared"`` or ``"completed"``.
    """

    stage: str
    workspace: str
    inputs: Mapping[str, str] = field(default_factory=dict)
    outputs: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)
    status: str = "prepared"
    schema_version: int = 1
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def path(self) -> Path:
        """Return the workspace-local manifest path."""
        return Path(self.workspace) / MANIFEST_NAME


def write_manifest(manifest: StageManifest) -> Path:
    """Write a stage manifest atomically as formatted JSON."""
    destination = manifest.path
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return destination


def read_manifest(workspace: str | Path, *, expected_stage: str | None = None) -> StageManifest:
    """Read and validate a workspace manifest.

    Raises
    ------
    ArtifactError
        If the file is absent, malformed, or belongs to a different stage.
    """
    path = Path(workspace) / MANIFEST_NAME
    if not path.is_file():
        raise ArtifactError(f"Manifesto de artefatos ausente: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"Manifesto inválido: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ArtifactError(f"Manifesto inválido: raiz não é objeto JSON: {path}")
    try:
        manifest = StageManifest(
            stage=str(raw["stage"]),
            workspace=str(raw["workspace"]),
            inputs=dict(raw.get("inputs", {})),
            outputs=dict(raw.get("outputs", {})),
            metadata=dict(raw.get("metadata", {})),
            status=str(raw.get("status", "prepared")),
            schema_version=int(raw.get("schema_version", 1)),
            created_at_utc=str(raw.get("created_at_utc", "")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ArtifactError(f"Manifesto inválido: {path}: {exc}") from exc
    if expected_stage and manifest.stage != expected_stage:
        raise ArtifactError(
            f"Manifesto {path} pertence à etapa '{manifest.stage}', esperado '{expected_stage}'."
        )
    return manifest
