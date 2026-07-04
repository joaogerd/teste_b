"""Named final products of the MPAS-JEDI/SABER static B-matrix workflow."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BMatrixProducts:
    """Paths to reusable B-matrix artifacts and core diagnostics.

    The files in :meth:`required_for_assimilation` are the minimal artifacts
    consumed by a later MPAS-JEDI/SABER 3DVar/FGAT configuration.  Correlation
    and DIRAC files remain first-class diagnostics and provenance products.
    """

    vbal: Path
    sampling: Path
    stddev: Path
    cor_rh: Path
    cor_rv: Path
    nicas: Path
    nicas_norm: Path
    dirac_nicas: Path
    dirac: Path

    @classmethod
    def from_workspaces(
        cls,
        *,
        vbal_workspace: str | Path,
        hdiag_workspace: str | Path,
        nicas_workspace: str | Path,
        dirac_workspace: str | Path | None = None,
    ) -> "BMatrixProducts":
        """Build canonical product paths from stage workspace roots."""
        vbal = Path(vbal_workspace) / "VBAL"
        hdiag = Path(hdiag_workspace) / "HDIAG"
        nicas = Path(nicas_workspace) / "merge"
        nicas_root = Path(nicas_workspace)
        dirac_root = Path(dirac_workspace) if dirac_workspace is not None else nicas_root.parent.parent / "dirac" / nicas_root.name
        return cls(
            vbal=vbal / "mpas_vbal.nc",
            sampling=vbal / "mpas_sampling.nc",
            stddev=hdiag / "mpas.stddev.nc",
            cor_rh=hdiag / "mpas.cor_rh.nc",
            cor_rv=hdiag / "mpas.cor_rv.nc",
            nicas=nicas / "mpas_nicas.nc",
            nicas_norm=nicas / "mpas.nicas_norm.nc",
            dirac_nicas=nicas / "mpas.dirac_nicas.nc",
            dirac=dirac_root / "mpas.dirac.nc",
        )

    def required_for_assimilation(self) -> tuple[Path, ...]:
        """Return the minimal local/global B products required by SABER."""
        return (self.vbal, self.sampling, self.stddev, self.nicas)
