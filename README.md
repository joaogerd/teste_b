# MPAS-BMatrix

`MPAS-BMatrix` is the official Python orchestration repository for building,
validating and diagnosing static MPAS-JEDI/SABER/BUMP background-error
covariance products for a global MPAS workflow.

The package exposes one public command:

```bash
mpas-bmatrix
```

The repository starts at the **BFLOW** boundary. It assumes that MPAS forecasts
and same-valid-time NMC pairs already exist. In the current workflow those
upstream pairs are generated with the external `mpaswf` workflow, then consumed
here to prepare perturbations and calibrate the B-matrix products.

## What the B-matrix represents

In variational data assimilation, the background-error covariance matrix `B`
controls how observational information spreads from the observation location into
the analysis state:

```text
- horizontally;
- vertically;
- between variables;
- with a prescribed/statistically estimated amplitude.
```

In MPAS-JEDI/SABER, the static B is represented by operators and files rather
than by one dense matrix:

```text
B ≈ C2A · VBAL · StdDev · NICAS · StdDev · VBALᵀ · C2Aᵀ
```

where `NICAS` represents spatial correlations, `StdDev` represents error
amplitudes, `VBAL` represents vertical/multivariate balance, and `C2A` is the
`Control2Analysis` variable change.

The complete workflow is:

```text
mpaswf -> BFLOW -> VBAL -> UNBALANCE -> HDIAG -> NICAS -> SO -> DIRAC -> PLOTS
```

`UNBALANCE` is intentionally explicit in this repository: VBAL calibrates the
balance transform, UNBALANCE writes the unbalanced training members, and HDIAG
uses those members for the statistics.

For the scientific explanation of each stage, see
[`docs/bmatrix-theory.md`](docs/bmatrix-theory.md).

## Recommended checkout layout

Use a project area and a separate work area. The paths below are examples; adapt
only the exported roots for your account, project, or machine.

```bash
export PROJECT_ROOT=/path/to/projects
export WORK_ROOT=/path/to/work/MPAS-BMatrix

mkdir -p "$PROJECT_ROOT" "$WORK_ROOT"
cd "$PROJECT_ROOT"

git clone https://github.com/joaogerd/MPAS-BMatrix.git
git clone https://github.com/joaogerd/mpaswf.git

export BMATRIX_ROOT="$PROJECT_ROOT/MPAS-BMatrix"
export MPASWF_ROOT="$PROJECT_ROOT/mpaswf"
```

Install both repositories in the environment you will use:

```bash
python -m pip install --no-deps -e "$MPASWF_ROOT"
python -m pip install -e "$BMATRIX_ROOT"
```

On JACI, source the repository-local loader from the B-matrix checkout. The
loader is path-generic; set `STACK_ROOT` for your spack-stack environment first.

```bash
cd "$BMATRIX_ROOT"
export STACK_ROOT=/path/to/spack-stack
source scripts/load_jaci_env.sh
```

## Workflow boundary

```text
External upstream:
  mpaswf
    -> GFS/WPS/ungrib
    -> mpas_init_atmosphere
    -> MPAS forecasts f024/f048
    -> same-valid-time NMC forecast-pair manifest

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
  jaci-x1.10242.yaml        # platform paths, mesh, executables, PBS and environment
  bmatrix-x1.10242.yaml     # scientific B-matrix contract

scripts/
  load_jaci_env.sh          # repository-local JACI MPAS-JEDI environment loader

src/bmatrix/
  cli.py                    # single public CLI
  pipeline.py               # dependency-ordered orchestration
  *_core/                   # stage-specific prepare/submit/check logic
  plots_core/               # diagnostic plotting stage
  scheduler/                # PBS submission/progress helpers

docs/
  README.md                 # documentation index
  bmatrix-theory.md         # theory and meaning of each stage
  mpaswf-pairs.md           # upstream pair generation with mpaswf
  workflow.md               # end-to-end workflow and stage ownership
  scientific-contract.md    # variables, aliases, B blocks and products
  jaci-quickstart.md        # generic JACI commands
  diagnostics-and-plots.md  # plot products and visual checks
  operations.md             # validation, provenance and troubleshooting
  refactoring.md            # implementation notes from the refactor
```

## Installation

Install the base package:

```bash
cd "$BMATRIX_ROOT"
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

Install the upstream MPAS workflow:

```bash
cd "$MPASWF_ROOT"
python -m pip install --no-deps -e .
```

## Quick start

```bash
cd "$BMATRIX_ROOT"

CONFIG=configs/jaci-x1.10242.yaml
BFLOW="$WORK_ROOT/bmatrix/bflow_preprocessing/np128_<START_VALID>_<END_VALID>"
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

## Main commands

```bash
mpas-bmatrix check-config --config configs/jaci-x1.10242.yaml
mpas-bmatrix weights       --config configs/jaci-x1.10242.yaml --bflow-workspace <BFLOW>
mpas-bmatrix build         --config configs/jaci-x1.10242.yaml --bflow-workspace <BFLOW>
mpas-bmatrix validate      --config configs/jaci-x1.10242.yaml --bflow-workspace <BFLOW> --stage <stage>
mpas-bmatrix plots         --config configs/jaci-x1.10242.yaml --bflow-workspace <BFLOW>
mpas-bmatrix products      --config configs/jaci-x1.10242.yaml --bflow-workspace <BFLOW>
```

Valid stages are:

```text
bflow, vbal, unbalance, hdiag, nicas, so, dirac, plots
```

## Generating pairs with mpaswf

Generate MPAS f024/f048 forecasts and the forecast-pair manifest before running
this package:

```bash
cd "$MPASWF_ROOT"
MPASWF_CONFIG=/path/to/mpaswf-config.yaml

mpaswf run --phase prepare  --config "$MPASWF_CONFIG"
mpaswf run --phase init     --config "$MPASWF_CONFIG" --submit --wait
mpaswf run --phase forecast --config "$MPASWF_CONFIG" --submit --wait
mpaswf run --phase manifest --config "$MPASWF_CONFIG"
```

Then use the generated manifest in this package:

```bash
cd "$BMATRIX_ROOT"
MANIFEST=/path/to/mpaswf-work/products/mpas-forecast-manifest.tsv

PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix build \
  --config "$CONFIG" \
  --manifest "$MANIFEST" \
  --from-stage bflow \
  --to-stage plots \
  --clean \
  --poll-seconds 30
```

For details, see [`docs/mpaswf-pairs.md`](docs/mpaswf-pairs.md).

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
9. Do not use `/tmp` for persistent audits or reproducibility logs.

## Development checks

Run these before merging documentation or code changes:

```bash
cd "$BMATRIX_ROOT"
mkdir -p .pytest-tmp

TMPDIR="$BMATRIX_ROOT/.pytest-tmp" \
PYTHONPATH="src:${PYTHONPATH:-}" \
python -m pytest -p no:cacheprovider -q

python -m ruff check src/bmatrix tests

git diff --check
```

## Documentation

Start with [`docs/README.md`](docs/README.md) and
[`docs/bmatrix-theory.md`](docs/bmatrix-theory.md). For the full operational
flow, read [`docs/workflow.md`](docs/workflow.md),
[`docs/mpaswf-pairs.md`](docs/mpaswf-pairs.md) and
[`docs/jaci-quickstart.md`](docs/jaci-quickstart.md). For variable names,
aliases and SABER/BUMP contracts, read
[`docs/scientific-contract.md`](docs/scientific-contract.md).
