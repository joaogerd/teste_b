# MPAS B-Matrix Global — guia da arquitetura refatorada

O pacote possui **um único comando público**:

```bash
mpas-bmatrix --help
```

Ele recebe pares NMC já produzidos, prepara as amostras BFLOW e executa, na
ordem de dependência, as etapas `VBAL`, `UNBALANCE`, `HDIAG`, `NICAS`, `SO` e
`DIRAC`.

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

UNBALANCE/samplesUnbalanced:
  PTB_f48mf24_*.nc

HDIAG/HDIAG:
  mpas.stddev.nc
  mpas.cor_rh.nc
  mpas.cor_rv.nc

NICAS/merge:
  mpas_nicas.nc
  mpas_nicas_local_*
  mpas_nicas_grids_local_*
```

Os arquivos NICAS locais preservam a dimensionalidade vertical de cada grupo.
No x1.10242, `stream_function`, `velocity_potential`, `temperature` e
`spechum` sao grupos 3D com `nl0 = 55`, enquanto `surface_pressure` e 2D e
usa `nl0 = 1`. Por isso, os YAMLs de SO e DIRAC declaram `read.grids` no bloco
`BUMP_NICAS`: uma grade para as quatro variaveis 3D e outra grade contendo
somente `surface_pressure`. Sem essa separacao, o leitor local do BUMP usa a
geometria 3D efetiva para todos os grupos e aborta com `wrong size for
dimension nl0` ao chegar em `surface_pressure`.

Produtos de diagnóstico produzidos ou preservados:

```text
NICAS/merge/mpas.nicas_norm.nc
NICAS/merge/mpas.dirac_nicas.nc
DIRAC/mpas.dirac.nc
SO/obsout_SO_*.h5
SO/an.*.nc
```

A composicao `StdDev + NICAS + VBAL + Control2Analysis` opera, em SO e
DIRAC, no espaço canônico do JEDI/OOPS. Esses nomes canônicos não são campos
de stream MPAS. O stream MPAS valida nomes contra o Registry e rejeita, por
exemplo, `eastward_wind` quando usado em `stream_list.atmosphere.analysis`.
Por isso `SO/an.*.nc` permanece MPAS-nativo; ele serve para confirmar que a
aplicação variacional escreveu um estado MPAS válido, enquanto a resposta
canônica deve ser diagnosticada no log/OOPS ou por uma saída diagnóstica
dedicada futura.

Nos aliases, `in code` e o nome interno esperado pelo MPAS-JEDI/SABER/OOPS
novo, e `in file` e o nome existente nos produtos NetCDF da B. O alias
`in code`/`in file` vale para JEDI/SABER/BUMP lendo esses produtos; ele nao
traduz nomes para o parser de streams do MPAS. Por isso SO/DIRAC reutilizam os
arquivos `streams.atmosphere_240km` e `stream_list.atmosphere.*` compatíveis
com a física, packages e Registry da configuração original. Nao se deve criar
manualmente uma lista mínima de campos de análise sem validá-la contra o parser
MPAS; mesmo campos MPAS nativos podem ser rejeitados nessa combinação. Um
diagnostico numerico da resposta canonica deve ser implementado separadamente
no futuro, por exemplo por saida diagnostica JEDI/FieldSet ou outro mecanismo
especifico.

A etapa DIRAC gera `mpas.dirac.nc` usando os parâmetros de impulso
declarados em `dirac` e a mesma B completa validada por SO.

## UNBALANCE e K2

VBAL estima os coeficientes usados pela transformação vertical `K2`. A etapa
UNBALANCE aplica `K2^-1` com `mpasjedi_unbalance_ensemble.x`, lendo os membros
centrados em `samples` e escrevendo `samplesUnbalanced` em CDF5. HDIAG não usa
PTBs brutos; ele consome exclusivamente esses membros no espaço
desbalanceado.

O tutorial NCAR usa `samplesUnbalanced` como contrato de entrada para HDIAG,
mas não expõe no fluxo público uma etapa reprodutível para escrever esses
arquivos. Esta implementação torna a escrita explícita, registra o executável
no manifesto e bloqueia HDIAG se os quatro membros CDF5 esperados estiverem
ausentes ou inválidos.

O round-trip `K2(K2^-1(PTB_i - mean(PTB)))` foi validado contra
`PTB_i - mean(PTB)` para os quatro membros e as variáveis `stream_function`,
`spechum`, `velocity_potential`, `temperature` e `surface_pressure`.
