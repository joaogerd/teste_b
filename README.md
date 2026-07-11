# MPAS-BMatrix

Geração dos produtos de uma matriz B estática MPAS-JEDI/SABER a partir de pares
NMC já existentes. A ferramenta possui **um único executável público**:

```bash
mpas-bmatrix
```

O escopo começa no BFLOW: previsões MPAS f024/f048 e seus pares de mesmo tempo
válido são entradas externas. WPS, download de GFS, `init_atmosphere` e forecast
não são responsabilidade deste pacote.

## Produtos científicos

A matriz B reutilizável é um conjunto de produtos, não um NetCDF único:

```text
BFLOW  -> FULL_f24.nc, FULL_f48.nc, PTB_f48mf24.nc
VBAL   -> mpas_vbal.nc, mpas_sampling.nc e produtos locais
UNBALANCE -> samplesUnbalanced/PTB_f48mf24_*.nc
HDIAG  -> mpas.stddev.nc, mpas.cor_rh.nc, mpas.cor_rv.nc
NICAS  -> mpas_nicas.nc, mpas_nicas_local_*, mpas_nicas_grids_local_*,
          mpas.nicas_norm.nc e mpas.dirac_nicas.nc
SO     -> an.*.nc e obsout_SO_*.h5 (validação com assimilação)
DIRAC  -> mpas.dirac.nc (resposta da B completa a um impulso)
PLOTS  -> summary.csv, README.md e figuras PNG de diagnóstico
```

A configuração e o layout dos produtos correspondem ao contrato científico
do projeto. DIRAC é renderizado a partir dos parâmetros declarados em `dirac` e
usa a mesma composição SABER de NICAS + StdDev + VBAL + Control2Analysis.

Na leitura local de `BUMP_NICAS`, SO e DIRAC separam explicitamente as grades
por dimensionalidade vertical: `stream_function`, `velocity_potential`,
`temperature` e `spechum` ficam na grade 3D, enquanto `surface_pressure` fica
sozinha na grade 2D. O produto NICAS merge continua contendo todos os grupos,
mas essa divisão evita que o BUMP aplique `nl0=55` ao grupo `surface_pressure`,
que e gravado com `nl0=1`.

SO e DIRAC aplicam `Control2Analysis` no espaço canônico interno do JEDI/OOPS
(`eastward_wind`, `northward_wind`, `air_temperature`,
`water_vapor_mixing_ratio_wrt_moist_air`, `air_pressure_at_surface`). O stream
MPAS, porém, grava apenas variáveis registradas no MPAS Registry. Assim,
`SO/an.*.nc` é uma saída MPAS-nativa (`uReconstruct*`, `theta`, `qv`,
`surface_pressure`, etc.), não um arquivo no espaço canônico JEDI. A resposta
canônica do SO deve ser conferida no log/OOPS ou por uma futura saída
diagnóstica dedicada, não pelo stream MPAS padrão.

Nos blocos de alias, `in code` é o nome esperado internamente pelo código
novo MPAS-JEDI/SABER/OOPS, enquanto `in file` é o nome gravado nos produtos
NetCDF da B. Esse alias é consumido por JEDI/SABER/BUMP ao ler os produtos da
B; ele não é aplicado pelo parser de streams do MPAS. Portanto,
SO e DIRAC reutilizam os arquivos `streams.atmosphere_240km` e
`stream_list.atmosphere.*` compatíveis com a física, packages e Registry da
configuração original. Não se deve criar manualmente uma lista mínima de campos
de análise sem validá-la contra o parser MPAS; mesmo campos MPAS nativos podem
ser rejeitados nessa combinação. O diagnóstico numérico da resposta canônica
deve ser uma etapa futura separada, por exemplo via saída diagnóstica
JEDI/FieldSet ou mecanismo específico.

## Etapa UNBALANCE

O fluxo científico é:

```text
BFLOW -> VBAL -> UNBALANCE -> HDIAG -> NICAS -> SO -> DIRAC -> PLOTS
```

VBAL calibra os coeficientes da transformação vertical `K2`. UNBALANCE aplica
`K2^-1` aos PTBs centrados por meio de `mpasjedi_unbalance_ensemble.x` e grava
`samplesUnbalanced`. Esses arquivos não são os PTBs brutos: são anomalias
centradas no espaço desbalanceado, usadas como entrada exclusiva do HDIAG.

O tutorial NCAR declara `samplesUnbalanced` como entrada do HDIAG, mas o fluxo
público atual não fornece uma escrita reproduzível desses membros. Por isso a
aplicação de `K2^-1` é uma etapa explícita, com PBS, manifesto e validação de
CDF5. A reversibilidade foi verificada numericamente por round-trip:
`K2(K2^-1(PTB_i - mean(PTB))) ~= PTB_i - mean(PTB)` para os quatro membros e
as cinco variáveis de controle.

## Etapa PLOTS

`PLOTS` é uma etapa local de pós-processamento. Ela não submete PBS e não altera
os produtos científicos; apenas lê os NetCDF finais, gera `summary.csv`, um
`README.md` de proveniência e figuras PNG simples.

A saída padrão é determinística a partir do workspace BFLOW:

```text
${work_root}/bmatrix/plots/<RUN_ID>/
```

A plotagem usa `lonCell`/`latCell` quando essas coordenadas estão disponíveis e
cai para gráficos por índice quando o produto não contém coordenadas de malha.
Assim, a etapa funciona sem Cartopy; `matplotlib` é a única dependência
diagnóstica adicional.

## Instalação

```bash
python -m pip install -e .
# geração de pesos e transformação psi/chi exigem dependências compiladas:
conda install -c conda-forge esmpy windspharm pyspharm
# plotagem diagnóstica:
python -m pip install -e ".[diagnostics]"
```

## Uso

Valide a configuração mesclada:

```bash
mpas-bmatrix check-config --config configs/jaci-x1.10242.yaml
```

Mostre o plano sem criar arquivos ou submeter PBS:

```bash
mpas-bmatrix build \
  --config configs/jaci-x1.10242.yaml \
  --manifest /dados/nmc/manifest.tsv \
  --dry-run
```

Execute a construção completa, esperando cada dependência PBS terminar antes da
etapa seguinte:

```bash
mpas-bmatrix build \
  --config configs/jaci-x1.10242.yaml \
  --manifest /dados/nmc/manifest.tsv \
  --poll-seconds 30
```

Para produzir também a pós-plotagem no fim do fluxo:

```bash
mpas-bmatrix build \
  --config configs/jaci-x1.10242.yaml \
  --manifest /dados/nmc/manifest.tsv \
  --to-stage plots \
  --plot-level 30
```

Para produzir somente a B reutilizável, sem o teste SO:

```bash
mpas-bmatrix build \
  --config configs/jaci-x1.10242.yaml \
  --manifest /dados/nmc/manifest.tsv \
  --to-stage nicas
```

Executar apenas a aplicação de `K2^-1` a partir de um workspace BFLOW já
preparado e com VBAL validado:

```bash
mpas-bmatrix build \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace /caminho/para/workspace-bflow \
  --from-stage unbalance \
  --to-stage unbalance
```

Executar UNBALANCE seguido de HDIAG:

```bash
mpas-bmatrix build \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace /caminho/para/workspace-bflow \
  --from-stage unbalance \
  --to-stage hdiag
```

Gerar apenas figuras e resumos a partir de produtos já concluídos:

```bash
mpas-bmatrix plots \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace /caminho/para/workspace-bflow \
  --plot-level 30 \
  --plot-dpi 150
```

## PBS progress display

When the command is running in an interactive terminal, every PBS dependency is
monitored with a compact colored braille spinner. The row shows the job ID,
current PBS state, elapsed time, and time until the next `qstat` query.

```text
⠹ PBS job 289521.pbs-ha: state R elapsed 02:14 next check in 18s
```

Finished jobs produce a persistent green confirmation before output validation.
When stdout is redirected, the command writes periodic `[RUN]` lines instead of
ANSI control characters, preserving readable logs.

Color follows terminal capability by default. Set one of the following values
when needed:

```bash
MPAS_BMATRIX_COLOR=always mpas-bmatrix build ...
MPAS_BMATRIX_COLOR=never mpas-bmatrix build ...
NO_COLOR=1 mpas-bmatrix build ...
```

The scheduler query cadence remains controlled by `--poll-seconds`; the spinner
animates between queries and does not increase scheduler load.

Os pesos ESMF são gerados por ESMPy integrado ao pacote; não há NCL, SCRIP ou
outro executável de pesos. Cada workspace BFLOW grava
`ESMF_weights/weights_manifest.json` com checksum e validação dos pesos.

## Configuração

- `configs/jaci-x1.10242.yaml`: plataforma, caminhos, MPI, PBS e executáveis.
- `configs/bmatrix-x1.10242.yaml`: controles, BFLOW, VBAL, HDIAG, NICAS, SO e DIRAC.

A configuração da plataforma referencia o contrato científico por
`bmatrix.configuration`. Os mapas são combinados por *deep merge*; listas são
atômicas para evitar concatenação científica acidental.

## Proveniência

Toda etapa preparada ou concluída grava `stage-manifest.json`. Os manifestos
substituem o uso de README como contrato operacional e registram workspaces,
entradas, saídas, membros e variantes.
