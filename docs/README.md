# Documentation index

This directory documents the `main` branch of `joaogerd/teste_b`, the
`mpas-bmatrix-global` package used to build static MPAS-JEDI/SABER/BUMP
B-matrix products from already generated NMC forecast pairs.

## Start here

| Document | Purpose |
| --- | --- |
| [`workflow.md`](workflow.md) | End-to-end ownership from external `mpaswf` pairs to B-matrix products. |
| [`mpaswf-pairs.md`](mpaswf-pairs.md) | How to generate f024/f048 MPAS NMC forecast pairs and the manifest with `mpaswf`. |
| [`scientific-contract.md`](scientific-contract.md) | Variable names, aliases, SABER/BUMP blocks, `Control2Analysis`, UNBALANCE and DIRAC contract. |
| [`jaci-quickstart.md`](jaci-quickstart.md) | Commands for the validated JACI x1.10242 workflow. |
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

## Current validated case

The documentation assumes the global MPAS tutorial mesh and JACI paths declared
in:

```text
configs/jaci-x1.10242.yaml
configs/bmatrix-x1.10242.yaml
```

The validated BFLOW workspace used during development was:

```text
/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/bflow_preprocessing/np128_2026062200_2026062500
```

Use the same contract when comparing outputs or debugging stage regressions.
