# Refatoração entregue

## Escopo

Esta versão transforma o repositório em uma aplicação única para gerar e validar
os produtos de matriz B estática MPAS-JEDI/SABER a partir de pares NMC já
existentes. A aplicação não tenta controlar download de GFS, WPS, inicialização
MPAS ou forecasts: esses processos são produtores externos dos pares NMC.

## Interface pública

Há somente um entry point instalado:

```bash
mpas-bmatrix
```

Subcomandos:

```text
check-config  valida e mostra a configuração resolvida
weights       gera apenas os pesos ESMF via ESMPy
build         executa uma faixa de etapas
validate      valida uma etapa concluída
products      mostra caminhos dos produtos finais
```

## Etapas implementadas

```text
BFLOW → VBAL → HDIAG → NICAS → SO → DIRAC
```

O comando `build` aguarda a conclusão PBS de cada dependência antes de iniciar
a próxima etapa. `--dry-run` produz um plano sem criar arquivos, importar ESMPy,
NetCDF4 ou windspharm, ou submeter jobs.

## Pesos ESMF

O código do pacote fornecido `esmf_weights.zip` foi incorporado em
`bmatrix.esmf_weights`. A integração é feita por `bflow_core.weights`; não há
mais uma segunda implementação de malha/ESMF dentro do BFLOW, nem uso de NCL,
SCRIP ou executável externo de pesos.

## Produtos

A execução completa produz os produtos previstos para a B:

```text
BFLOW: FULL_f24.nc, FULL_f48.nc, PTB_f48mf24.nc
VBAL:  mpas_vbal.nc, mpas_sampling.nc e produtos MPI locais
HDIAG: mpas.stddev.nc, mpas.cor_rh.nc, mpas.cor_rv.nc
NICAS: mpas_nicas.nc, produtos MPI locais, mpas.nicas_norm.nc,
       mpas.dirac_nicas.nc
SO:    an.*.nc e obsout_SO_*.h5
DIRAC: mpas.dirac.nc
```

Os produtos de uso operacional da B permanecem NICAS + StdDev + VBAL. SO e
DIRAC são diagnósticos da B completa.

## Configuração

- `configs/jaci-x1.10242.yaml`: plataforma, executáveis, malha, PBS e ambiente.
- `configs/bmatrix-x1.10242.yaml`: contrato científico.

O carregador faz *deep merge*, expande variáveis de ambiente e preserva listas
como unidades atômicas. Nomes de produtos BFLOW, controles, relações VBAL,
comprimentos HDIAG, pontos NICAS, observações SO e impulso DIRAC são lidos do
YAML; não permanecem duplicados como constantes de aplicação.

## Proveniência e dependências

Cada etapa grava `stage-manifest.json`; etapas posteriores usam esse manifesto,
não README, para localizar entradas e saídas.

## Verificações executadas nesta entrega

```text
python -m compileall -q src
pytest -q                         # 9 testes aprovados
python -m pip install --no-deps -e .
mpas-bmatrix --help
mpas-bmatrix check-config --config configs/jaci-x1.10242.yaml
mpas-bmatrix build ... --dry-run
```

A execução completa ainda deve ser submetida no JACI para validar a
compatibilidade exata da versão instalada do `mpasjedi_error_covariance_toolbox.x`
com o YAML DIRAC, bem como os produtos científicos produzidos com uma amostra
real de pares NMC.
