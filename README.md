# mpas-bmatrix-global

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
HDIAG  -> mpas.stddev.nc, mpas.cor_rh.nc, mpas.cor_rv.nc
NICAS  -> mpas_nicas.nc, mpas_nicas_local_*, mpas_nicas_grids_local_*,
          mpas.nicas_norm.nc e mpas.dirac_nicas.nc
SO     -> an.*.nc e obsout_SO_*.h5 (validação com assimilação)
DIRAC  -> mpas.dirac.nc (resposta da B completa a um impulso)
```

A configuração e o layout dos produtos correspondem ao contrato científico
do projeto. DIRAC é renderizado a partir dos parâmetros declarados em `dirac` e
usa a mesma composição SABER de NICAS + StdDev + VBAL + Control2Analysis.

## Instalação

```bash
python -m pip install -e .
# geração de pesos e transformação psi/chi exigem dependências compiladas:
conda install -c conda-forge esmpy windspharm pyspharm
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

Para produzir somente a B reutilizável, sem o teste SO:

```bash
mpas-bmatrix build \
  --config configs/jaci-x1.10242.yaml \
  --manifest /dados/nmc/manifest.tsv \
  --to-stage nicas
```

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
