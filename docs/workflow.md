# Workflow

This document describes the operational flow represented by the `main` branch.

## 1. Upstream pair generation

The NMC forecast pairs are generated before this package starts. The operational
tool used for that upstream step is `mpaswf`.

The upstream chain is:

```text
GFS GRIB2
  -> WPS/ungrib
  -> FILE:YYYY-MM-DD_HH
  -> mpas_init_atmosphere
  -> MPAS initial conditions
  -> MPAS atmosphere forecasts f024 and f048
  -> same-valid-time forecast pair
  -> NMC difference f048 - f024
```

The B-matrix package does not rerun this meteorological workflow. It consumes
the results as a manifest or as an already prepared BFLOW workspace.

The `mpaswf` public phases are:

```bash
mpaswf run --phase prepare  --config "$MPASWF_CONFIG"
mpaswf run --phase init     --config "$MPASWF_CONFIG" --submit --wait
mpaswf run --phase forecast --config "$MPASWF_CONFIG" --submit --wait
mpaswf run --phase manifest --config "$MPASWF_CONFIG"
```

The manifest produced by `mpaswf` is the upstream hand-off file:

```text
<mpaswf work_dir>/products/mpas-forecast-manifest.tsv
```

It contains one row per same-valid-time pair and uses these columns:

```text
valid_time    f048_state    f024_state    f048_restart    f024_restart
```

This package can start from that manifest:

```bash
PYTHONPATH="src:${PYTHONPATH:-}" python -m bmatrix build \
  --config "$CONFIG" \
  --manifest "$MANIFEST" \
  --from-stage bflow \
  --to-stage plots \
  --clean \
  --poll-seconds 30
```

For the complete upstream procedure, including MPASWF configuration and PBS
execution patterns, see [`mpaswf-pairs.md`](mpaswf-pairs.md).

Keep this separation:

```text
mpaswf
  produces MPAS states and NMC forecast pairs

mpas-bmatrix BFLOW
  transforms those pairs into FULL and PTB products

SABER/BUMP stages
  calibrate, validate and diagnose the static B-matrix
```

## 2. BFLOW

BFLOW is the boundary stage. It prepares MPAS/JEDI control-space perturbations
from NMC forecast pairs.

Expected products:

```text
FULL_f24.nc
FULL_f48.nc
PTB_f48mf24.nc
template_PTB.nc
manifest.tsv
ESMF_weights/weights_manifest.json
```

BFLOW uses the scientific contract in `configs/bmatrix-x1.10242.yaml`:

- `bflow.nmc` declares the NMC lead times: f048 minus f024.
- `bflow.products` declares product names.
- `bflow.regridding` owns the MPAS-to-latlon weight configuration.
- `bflow.wind_transform` declares the conversion to streamfunction and velocity
  potential.
- `bflow.derived_variables` creates analysis/control variables such as air
  temperature and specific humidity from MPAS-native fields.

## 3. VBAL

VBAL estimates the vertical-balance coefficients used by the `K2` transform.

Expected products:

```text
VBAL/mpas_vbal.nc
VBAL/mpas_sampling.nc
VBAL/mpas_vbal_local_*
VBAL/mpas_sampling_local_*
```

VBAL is a calibration stage. It does not, by itself, provide a reliable public
contract for writing the final unbalanced ensemble members on disk.

## 4. UNBALANCE

UNBALANCE is an explicit stage added to materialize the members needed by HDIAG.

It applies `K2^-1` to centered perturbations and writes:

```text
samplesUnbalanced/PTB_f48mf24_001.nc
samplesUnbalanced/PTB_f48mf24_002.nc
samplesUnbalanced/PTB_f48mf24_003.nc
samplesUnbalanced/PTB_f48mf24_004.nc
```

Those files are not raw PTBs. They are centered perturbations in the unbalanced
control space. HDIAG must use these files exclusively.

## 5. HDIAG

HDIAG computes global diagnostics from `samplesUnbalanced`.

Expected products:

```text
HDIAG/mpas.stddev.nc
HDIAG/mpas.cor_rh.nc
HDIAG/mpas.cor_rv.nc
```

The HDIAG sampling must keep the distance extent below the default BUMP universe
radius. For the validated case:

```yaml
distance classes: 10
distance class width: 1000000.0
```

This keeps `(10 - 1) * 1000000` below the default BUMP limit.

## 6. NICAS

NICAS builds the local/global correlation model and normalization diagnostics.

Expected products:

```text
merge/mpas_nicas.nc
merge/mpas.nicas_norm.nc
merge/mpas.dirac_nicas.nc
mpas_nicas_local_*
mpas_nicas_grids_local_*
```

For SO and DIRAC reads, `BUMP_NICAS.read.grids` must split the controls by
vertical dimensionality:

```text
3D: stream_function, velocity_potential, temperature, spechum
2D: surface_pressure
```

Without this split, BUMP can try to read the 2D `surface_pressure` local NICAS
group using a 3D `nl0`, leading to `wrong size for dimension nl0`.

## 7. SO

SO is a variational single-observation validation of the complete B composition.

It exercises:

```text
BUMP_NICAS + StdDev + BUMP_VerticalBalance + Control2Analysis
```

Expected outputs:

```text
SO/an.*.nc
SO/obsout_SO_T.h5
SO/obsout_SO_U.h5
```

`SO/an.*.nc` is MPAS-native output written by MPAS streams. It is not expected to
contain canonical JEDI variables. A successful SO is identified by:

- final OOPS status `with status = 0`;
- `CostFunction::addIncrement: Analysis` in the runlog;
- obsout files;
- an MPAS-native `an.*.nc` in CDF5 format.

## 8. DIRAC

DIRAC applies a complete-B impulse response test.

The validated contract follows the functional main workflow:

```yaml
dirac:
  ndir: 1
  dirLats: [...]
  dirLons: [...]
  ildir: 10
  dirvar: air_temperature

output dirac:
  filename: ./mpas.dirac.nc
  date: '2026-06-22T00:00:00Z'
  stream name: control
```

Do not replace this with reduced `dirLevs`/`dirVars` lists without revalidating
the MPAS-JEDI/SABER contract.

Expected product:

```text
DIRAC/mpas.dirac.nc
```

## 9. PLOTS

PLOTS is local post-processing. It does not change scientific products.

Expected products:

```text
summary.csv
README.md
01_stddev/
02_corr_horizontal/
03_corr_vertical/
04_vbal/
05_dirac/
06_spatial_fields/
```

Use plots to check that B amplitudes, correlation scales, balance diagnostics
and DIRAC responses are physically plausible.
