# Principais mudanças desta refatoração

- Um único entry point instalado: `mpas-bmatrix`.
- Um orquestrador (`bmatrix.pipeline`) que representa plano, caminhos e etapas:
  BFLOW -> VBAL -> UNBALANCE -> HDIAG -> NICAS -> SO -> DIRAC.
- PBS centralizado em `bmatrix.scheduler`.
- Pesos ESMF internalizados em `bmatrix.esmf_weights`, sem NCL/SCRIP.
- BFLOW, VBAL, UNBALANCE e HDIAG agora usam os nomes declarados em
  `bflow.products`.
- VBAL e HDIAG convertem códigos JEDI de `controls` em nomes físicos NetCDF ao
  renderizar YAML.
- NICAS e SO consomem manifests de artefatos, não README.
- Rotinas de forecast, WPS e init MPAS foram removidas do pacote porque são
  pré-requisitos externos, e não produtos de matriz B.
- UNBALANCE é uma etapa explícita para aplicar `K2^-1` e produzir
  `samplesUnbalanced` antes de HDIAG.
- DIRAC é uma etapa explícita do mesmo orquestrador e produz `mpas.dirac.nc`.
- `--dry-run` não importa ESMPy, netCDF4 ou windspharm nem toca no filesystem.
