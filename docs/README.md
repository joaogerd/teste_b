# MPAS B-Matrix Global — guia da arquitetura refatorada

O pacote possui **um único comando público**:

```bash
mpas-bmatrix --help
```

Ele recebe pares NMC já produzidos, prepara as amostras BFLOW e executa, na
ordem de dependência, as etapas `VBAL`, `HDIAG`, `NICAS` e `SO`.

## Limite explícito de escopo

A geração de GFS/WPS, `init_atmosphere` e forecasts MPAS não faz parte deste
pacote. Eles são produtores externos dos pares NMC. Esta decisão evita misturar
pré-processamento meteorológico e calibração da matriz B no mesmo componente.

## Comandos

```bash
# Verificar o YAML resolvido e as regras estruturais.
mpas-bmatrix check-config --config configs/jaci-x1.10242.yaml

# Planejar sem criar arquivos, importar NetCDF ou submeter jobs.
mpas-bmatrix build \
  --config configs/jaci-x1.10242.yaml \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time 2026-06-13_00:00:00 \
  --dry-run

# Criar os pesos ESMPy necessários pelo BFLOW.
mpas-bmatrix weights \
  --config configs/jaci-x1.10242.yaml \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time 2026-06-13_00:00:00

# Executar o pipeline completo.
mpas-bmatrix build \
  --config configs/jaci-x1.10242.yaml \
  --manifest /caminho/para/pares-nmc.tsv
```

## ESMPy para pesos ESMF

A geração de pesos é uma biblioteca interna (`bmatrix.esmf_weights`), baseada
no código ESMF fornecido ao projeto. Ela usa ESMPy diretamente e não depende de
NCL, SCRIP nem de outro executável de pesos.

O bloco `bflow.regridding` contém a única fonte de configuração de malha e de
interpolação. Os pesos são gravados em `<BFLOW>/ESMF_weights/` e registrados no
manifesto do estágio.

## Produtos da matriz B

Produtos necessários para leitura da B pelo MPAS-JEDI/SABER:

```text
VBAL/VBAL:
  mpas_vbal.nc
  mpas_sampling.nc
  mpas_vbal_local_*
  mpas_sampling_local_*

HDIAG/HDIAG:
  mpas.stddev.nc
  mpas.cor_rh.nc
  mpas.cor_rv.nc

NICAS/merge:
  mpas_nicas.nc
  mpas_nicas_local_*
  mpas_nicas_grids_local_*
```

Produtos de diagnóstico produzidos ou preservados:

```text
NICAS/merge/mpas.nicas_norm.nc
NICAS/merge/mpas.dirac_nicas.nc
DIRAC/mpas.dirac.nc
SO/obsout_SO_*.h5
SO/an.*.nc
```

A etapa DIRAC gera `mpas.dirac.nc` usando os parâmetros de impulso
declarados em `dirac` e a mesma B completa validada por SO.
