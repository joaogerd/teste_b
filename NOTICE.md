# Proveniência de componentes

`src/bmatrix/esmf_weights/` deriva do código de geração de pesos fornecido em
`esmf_weights.zip` nesta solicitação. Ele foi incorporado como biblioteca
interna e adaptado para receber os valores de `mesh` e `bflow.regridding` da
configuração unificada, sem manter um segundo executável ou YAML independente.
