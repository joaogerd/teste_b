# Documentation index

This directory documents `MPAS-BMatrix`, the official MPAS-JEDI/SABER/BUMP
static B-matrix workflow repository.

## Start here

| Document | Purpose |
| --- | --- |
| [`bmatrix-theory.md`](bmatrix-theory.md) | Scientific meaning of the B-matrix and each workflow stage, including explicit UNBALANCE. |
| [`workflow.md`](workflow.md) | End-to-end ownership from external `mpaswf` pairs to B-matrix products. |
| [`mpaswf-pairs.md`](mpaswf-pairs.md) | How to generate f024/f048 MPAS NMC forecast pairs and the manifest with `mpaswf`. |
| [`scientific-contract.md`](scientific-contract.md) | Variable names, aliases, SABER/BUMP blocks, `Control2Analysis`, UNBALANCE and DIRAC contract. |
| [`jaci-quickstart.md`](jaci-quickstart.md) | Generic JACI-oriented commands for cloning, installing and running. |
| [`diagnostics-and-plots.md`](diagnostics-and-plots.md) | Plot products, visual diagnostics and style conventions. |
| [`operations.md`](operations.md) | Validation, manifests, failure triage and maintenance rules. |
| [`refactoring.md`](refactoring.md) | Summary of the refactored architecture. |

## Scope

The repository owns the stages starting at BFLOW:

```text
BFLOW -> VBAL -> UNBALANCE -> HDIAG -> NICAS -> SO -> DIRAC -> PLOTS
```

The repository does not own GFS download, WPS/ungrib, MPAS initialization or
forecast integration. In the current operational chain those upstream products
are generated with `mpaswf`, then passed into this package as NMC pairs or an
already prepared BFLOW workspace.

## Recommended checkout layout

Use generic roots and adapt only the exports to your system:

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

## Current validated case

The documentation assumes the global MPAS tutorial mesh and the scientific
contract declared in:

```text
configs/jaci-x1.10242.yaml
configs/bmatrix-x1.10242.yaml
```

A typical BFLOW workspace path follows this pattern:

```text
$WORK_ROOT/bmatrix/bflow_preprocessing/np128_<START_VALID>_<END_VALID>
```

Use the same stage contract when comparing outputs or debugging regressions.
