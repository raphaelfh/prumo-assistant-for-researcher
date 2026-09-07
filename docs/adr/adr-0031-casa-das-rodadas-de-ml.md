# ADR-0031 — Rodadas persistidas de ML vivem em `experiments/<run_id>/` na raiz

- Status: aceito
- Data: 2026-09-07
- Origem: auditoria de organização do `pj_piloto_genetica` (2026-09-06), item 4. Precedentes: [ADR-0022](adr-0022-layout-por-escopo.md) (`docs/` como raiz única de leitura), [ADR-0012](adr-0012-remocao-agents-ml.md) (o que o módulo `ml` é e não é).

## Contexto

O padrão define onde vive saída de máquina efêmera — `build/exports/` (gitignorado) e `reviews/<slug>/` — mas nunca definiu onde ficam **rodadas persistidas**: o bundle serializado, as figuras, as tabelas de métricas e o registro do que aquela rodada mostrou.

Sem regra, um projeto real dividiu isso em dois lugares: `studies/01_estudo/experiments/` para as vigentes e `docs/_archive/experiments/` para as superadas. A segunda é o problema concreto. `docs/` é a raiz única de leitura — é o que o `qmd` indexa e o que as skills de wiki varrem. Bundle `.joblib` ali polui o índice de busca do projeto sem nunca ser conteúdo de leitura, e o custo aparece em toda consulta ao wiki, não só em quem mexe no modelo.

## Decisão

Rodada persistida vive em `experiments/<run_id>/` na **raiz** do `pj_*`, ao lado de `build/` e `reviews/`, com `experiments/_archive/<run_id>/` para as superadas. Fora de `docs/`, portanto fora do índice de leitura.

O payload é do módulo `ml` (`templates/modules/ml/experiments/`), não do `pj_base`: um projeto sem ML não precisa aprender esta casa, e o Princípio VIII mede custo em conceitos que o pesquisador precisa aprender. Chega por `prumo add ml`.

O que descreve a rodada é versionado — `README.md`, métricas em CSV, figuras. O bundle serializado não: `experiments/.gitignore` exclui `*.joblib`, `*.pkl`, `*.pt`, `*.onnx`. O bundle se regenera a partir do código e dos dados, e alguns MB por rodada afundam um repo que já carrega PDFs. O `.gitignore` é próprio do diretório em vez de uma entrada no `.gitignore` da raiz porque `overlay` copia arquivos e não faz merge: um arquivo novo entra sem tocar no que o projeto já tem.

`prumo doctor` **não** cobra a existência de `experiments/`. O diretório é opcional mesmo com o módulo `ml` aplicado — um projeto pode não ter rodado nada ainda —, e transformar ausência em issue seria nag sem dano.

## Consequências

Todo `pj_*` com módulo `ml` passa a ter uma casa canônica. Projeto existente com bundle em `docs/` **não** é detectado: o `[fora_do_padrao]` trabalha com lista fechada de diretórios que um ADR aposentou, e `docs/_archive/experiments/` foi convenção local de um projeto, não padrão anterior. A migração é manual, com este ADR como referência. Se o caso reaparecer num segundo projeto, ele vira entrada na lista fechada.

A escolha por raiz em vez de `docs/studies/<slug>/experiments/` custa atribuição: num projeto com vários escopos, nada no caminho diz qual estudo gerou a rodada. O `README.md` da rodada é onde isso é declarado. A alternativa por escopo resolveria a atribuição reintroduzindo exatamente o dano que motivou o ADR.
