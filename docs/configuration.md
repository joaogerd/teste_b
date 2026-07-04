# Configuração

A configuração é formada por:

1. **plataforma**: caminhos, executáveis, PBS e ambiente;
2. **contrato científico**: `controls`, `bflow`, `vbal`, `hdiag`, `nicas` e
   `single_observation`.

`config.load_config()` aplica merge profundo, expande variáveis de ambiente e
rejeita substituições estruturais inválidas. O YAML é autoritativo: nomes de
produtos BFLOW, tempos NMC, variáveis de controle, relações VBAL, comprimentos
de escala HDIAG, pontos NICAS e observações SO são lidos da configuração.

Os artefatos de cada etapa ficam em `stage-manifest.json`. Etapas consumidoras
usam esse manifesto; não leem README como contrato operacional.
