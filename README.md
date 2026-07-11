# mpas-bmatrix-global

`mpas-bmatrix-global` is the Python orchestration package used to build and
validate static MPAS-JEDI/SABER/BUMP background-error covariance products for
the global MPAS `x1.10242` case on JACI.

The package exposes one public command:

```bash
mpas-bmatrix
```

The package starts at the **BFLOW** boundary. It assumes that MPAS forecasts and
same-valid-time NMC pairs already exist. In the current workflow those upstream
pairs are generated with the external `mpaswf` workflow, then consumed here to
prepare perturbations and calibrate the B-matrix products.

## Workflow boundary

```text
External upstream:
  mpaswf
    -> GFS/WPS/ungrib
    -> mpas_init_atmosphere
    -> MPAS forecasts f024/f048
    -> same-valid-time NMC forecast pairs

This package:
  BFLOW
    -> FULL_f24.nc, FULL_f48.nc, PTB_f48mf24.nc
  VBAL
    -> mpas_vbal.nc, mpas_sampling.nc, local VBAL/sampling products
  UNBALANCE
    -> samplesUnbalanced/PTB_f48mf24_*.nc
  HDIAG
    -> mpas.stddev.nc, mpas.cor_rh.nc, mpas.cor_rv.nc
  NICAS
    -> mpas_nicas.nc, mpas.nicas_norm.nc, mpas.dirac_nicas.nc
  SO
    -> single-observation variational validation
  DIRAC
    -> complete-B impulse response
  PLOTS
    -> summary tables and diagnostic figures
```

Forecast production, GFS download, WPS/ungrib, MPAS initialization and MPAS
forecast integration are intentionally outside this repository. Keep those steps
in `mpaswf` or another upstream producer. This repository owns the covariance
product contract, the SABER/BUMP YAML rendering, PBS orchestration, validation
and diagnostics.

## Repository layout

```text
configs/
  jaci-x1.10242.yaml        # JACI paths, mesh, executables, PBS and environment
  bmatrix-x1.10242.yaml     # scientific B-matrix contract

src/bmatrix/
  cli.py                    # single public CLI
  pipeline.py               # dependency-ordered orchestration
  *_core/                   # stage-specific prepare/submit/check logic
  plots_core/               # diagnostic plotting stage
  scheduler/                # PBS submission/progress helpers

docs/
  README.md                 # documentation index
  workflow.md               # end-to-end workflow and stage ownership
  scientific-contract.md    # variables, aliases, B blocks and products
  jaci-quickstart.md        # operational commands on JACI
  diagnostics-and-plots.md  # plot products and visual checks
  operations.md             # validation, provenance and troubleshooting
  refactoring.md            # implementation notes from the refactor
```

## Installation

Install the base package:

```bash
python -m pip install -e .
```

Optional extras:

```bash
# ESMPy weight generation
python -m pip install -e ".[weights]"

# BFLOW wind transform support
python -m pip install -e ".[bflow]"

# Diagnostic plotting
python -m pip install -e ".[diagnostics]"

# Tests and linting
python -m pip install -e ".[dev]"
```

On JACI, prefer the project environment loader before running the workflow:

```bash
source /p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global/scripts/load_jaci_env.sh
```

## Quick start on JACI

```bash
cd /p/projetos/monan_das/joao.gerd/projects/teste_b

CONFIG=configs/jaci-x1.10242.yaml
BFLOW=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/bflow_preprocessing/np128_2026062200_2026062500
```

Validate the merged configuration:

```bash
PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix check-config \
  --config "$CONFIG"
```

Run the full B-matrix workflow from an existing BFLOW workspace:

```bash
PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix build \
  --config "$CONFIG" \
  --bflow-workspace "$BFLOW" \
  --clean \
  --poll-seconds 30
```

Run through plots:

```bash
PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix build \
  --config "$CONFIG" \
  --bflow-workspace "$BFLOW" \
  --to-stage plots \
  --plot-level 30 \
  --plot-dpi 150 \
  --clean \
  --poll-seconds 30
```

Generate only plots from completed products:

```bash
PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix plots \
  --config "$CONFIG" \
  --bflow-workspace "$BFLOW" \
  --plot-level 30 \
  --plot-dpi 150 \
  --clean
```

## Main commands

```bash
mpas-bmatrix check-config --config configs/jaci-x1.10242.yaml
mpas-bmatrix weights       --config configs/jaci-x1.10242.yaml --bflow-workspace <BFLOW>
mpas-bmatrix build         --config configs/jaci-x1.10242.yaml --bflow-workspace <BFLOW>
mpas-bmatrix validate      --config configs/jaci-x1.10242.yaml --bflow-workspace <BFLOW> --stage <stage>
mpas-bmatrix plots         --config configs/jaci-x1.10242.yaml --bflow-workspace <BFLOW>
mpas-bmatrix products      --config configs/jaci-x1.10242.yaml --bflow-workspace <BFLOW>
```

Stage selection is explicit and resumable:

```bash
mpas-bmatrix build --config "$CONFIG" --bflow-workspace "$BFLOW" \
  --from-stage unbalance --to-stage hdiag --clean
```

Valid stages are:

```text
bflow, vbal, unbalance, hdiag, nicas, so, dirac, plots
```

## Scientific products

The reusable B-matrix is a product set, not a single NetCDF file:

```text
Required for later SABER use:
  VBAL/VBAL/mpas_vbal.nc
  VBAL/VBAL/mpas_sampling.nc
  HDIAG/HDIAG/mpas.stddev.nc
  NICAS/merge/mpas_nicas.nc

Core diagnostics:
  HDIAG/HDIAG/mpas.cor_rh.nc
  HDIAG/HDIAG/mpas.cor_rv.nc
  NICAS/merge/mpas.nicas_norm.nc
  NICAS/merge/mpas.dirac_nicas.nc
  DIRAC/mpas.dirac.nc
  SO/an.*.nc
  SO/obsout_SO_*.h5
  PLOTS/summary.csv
```

## Variable-name contract

The current MPAS-JEDI/SABER/OOPS code uses canonical names, while many B-matrix
NetCDF products are stored with historical MPAS/tutorial names. The YAML aliases
make that mapping explicit:

```yaml
- in code: air_temperature
  in file: temperature
- in code: water_vapor_mixing_ratio_wrt_moist_air
  in file: spechum
- in code: air_pressure_at_surface
  in file: surface_pressure
```

`in code` is the internal name expected by the new MPAS-JEDI/SABER/OOPS code.
`in file` is the name present in NetCDF B-matrix products. This alias is for
JEDI/SABER/BUMP product reading. It is **not** a translation layer for the MPAS
stream parser. MPAS streams still accept only MPAS Registry fields.

## Important invariants

Keep these rules unless a new audit proves otherwise:

1. Do not write canonical JEDI names into `stream_list.atmosphere.analysis`.
2. Keep simple and compound `in code`/`in file` aliases for NICAS and VBAL reads.
3. Keep `BUMP_NICAS.read.grids` split into 3D controls and 2D surface pressure.
4. Keep `Control2Analysis` after the SABER B blocks.
5. Keep `UNBALANCE` as an explicit stage before HDIAG.
6. Keep DIRAC on the functional contract using full `dirLats`/`dirLons` plus
   singular selectors.
7. Do not treat `an-bg = 0` for MPAS-native SO output fields as an automatic
   failure.
8. Keep final NetCDF products in CDF5 when the stage contract requires it.
9. Do not use `/tmp` for persistent audits or reproducibility logs on JACI.

## PBS progress display

Interactive PBS runs use a compact colored spinner with job ID, PBS state,
elapsed time and next `qstat` poll. Redirected output falls back to persistent
`[RUN]` log lines.

```bash
MPAS_BMATRIX_COLOR=always mpas-bmatrix build ...
MPAS_BMATRIX_COLOR=never  mpas-bmatrix build ...
NO_COLOR=1                mpas-bmatrix build ...
```

The scheduler cadence is still controlled by `--poll-seconds`; the spinner does
not increase scheduler load.

## Development checks

Run these before merging documentation or code changes:

```bash
TMPDIR=/p/projetos/monan_das/joao.gerd/projects/teste_b/.pytest-tmp \
PYTHONPATH="src:${PYTHONPATH:-}" \
python -m pytest -p no:cacheprovider -q

python -m ruff check src/bmatrix tests

git diff --check
```

## Documentation

Start with [`docs/README.md`](docs/README.md). For the full operational flow,
read [`docs/workflow.md`](docs/workflow.md) and
[`docs/jaci-quickstart.md`](docs/jaci-quickstart.md). For variable names,
aliases and SABER/BUMP contracts, read
[`docs/scientific-contract.md`](docs/scientific-contract.md).
