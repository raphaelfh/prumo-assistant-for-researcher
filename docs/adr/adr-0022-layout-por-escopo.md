# ADR-0022 — Layout por escopo: `docs/` como raiz única de leitura

- Status: aceito
- Data: 2026-08-09
- Origem: [[2026-08-08-layout-por-escopo-design]]

## Contexto
O `pj_*` tinha dois topos de leitura (`docs/` e `references/`), o manuscrito não tinha casa,
e o `pj_base` embutia estrutura de código que 4 de 5 arquétipos de pesquisador nunca abrem.

## Decisão
`docs/` é a raiz única de leitura. A bibliografia é do PROJETO e vive em `docs/references/`,
com `papers/<citekey>/` no lugar de `notes/<citekey>/`. `core/pj_layout.py` é a autoridade
única de caminho, com `find_pj_root` (sentinela `.claude/pj_config.toml`) separado de
`find_scope_root` (posição). Tudo que serve só a alguns arquétipos vira camada com gatilho
observável. Corte limpo: layout legado falha com convite à adequação agêntica.

## Consequências
O literal `"references"` não desaparece do código — reaparece como exclusão de varredura no
lint. `paper connect` segue exclusivo do Better BibTeX; o contrato do núcleo é BibTeX.
Projeto legado exige reconfigurar o autoexport do BBT, que guarda caminho absoluto.
