# ADR-0037 — Ponte Zotero mínima: anotações e notas saem do PAR; Better BibTeX só no connect e no lookup do docx

- Status: aceito
- Data: 2026-10-02
- Origem: [[2026-10-02-ponte-zotero-minima-design]]; emenda a ADR-0008, a ADR-0020 e a ADR-0026; substitui as linhas "Zotero/BBT fechado — caminho canônico" e "Pandoc embutido do Zettlr < 3.0" da tabela de degradações de [[2026-07-22-zettlr-front-design]]

## Contexto

O PAR falava com o Zotero por quatro caminhos: auto-export do `.bib`, lookup do docx, anotações e notas pela API local, e a sonda do doctor. A auditoria de 2026-08-23 (A6) achou 0 `_annotations.md` e 0 `note__*.md` em 14 projetos, e a recontagem de 2026-10, 0 em 15. Esse pipeline era o único consumidor da API local, e por causa dele o doctor exigia o toggle "Allow other applications". O docx tinha três defeitos que atingiam todo export padrão: `library=""` fazia o Better BibTeX recusar o lookup em silêncio; sem `uris`, o Refresh do Zotero no Word lançava TypeError; e o gate exigia o Zotero aberto para um lookup descartado. O Refresh também reescreve os campos e apaga as marcas do PAR, e o ingest recusava esse docx com uma mensagem enganosa.

## Decisão

1. Saem `paper sync-annotations`, `sync-notes` e `sync-all`, a tool MCP `paper_sync_all` (o servidor fica com 10 tools, 6 de `paper`), os re-exports da API, `ZoteroApiError`, `note_paths.child_note_path` e a regra `duplicate_item_key`. Arquivos legados continuam legíveis. O `migrate-layout` continua separando o bloco de anotações de uma nota plana antiga em `_annotations.md`. A spec [[2026-05-03-zotero-notes-integration-design]], que desenhou o `sync-notes`, passa a `superseded` na 0.71.0.
2. O Better BibTeX fica só onde é a única fonte: citation keys, `autoexport.add` no `connect` (guardas da ADR-0020 e da ADR-0028 intactas) e `item.pandoc_filter` no export docx. A API local `/api/*` não é usada. O toggle não é exigido. Não existe `core/zotero_local.py`: a API local exige o toggle e um módulo novo; o vínculo não é o motivo (`users/0` também religa).
3. O lookup do docx é melhor-esforço (2 s), sem gate. O terceiro parâmetro só vai quando há `zotero.library`. Cada citação leva `uris`, sempre como array JSON (`lookup.uri and { lookup.uri } or json.decode('[]')`). As citações sem vínculo geram um aviso por causa (inalcançável, sandbox do Claude Code, erro JSON-RPC, chave ausente), com o comando de refazer, que repete as opções da chamada original.
4. Contrato da rodada de revisão: sem Refresh nem Add/Edit Citation do Zotero no docx em revisão. A nota de primeiro uso diz isso, e o ingest recusa com mensagem própria qualquer campo sem `prumoOcc`, antes das demais checagens de conservação. A tolerância fica adiada (ROADMAP).
5. Base URL e URL do JSON-RPC únicas em `core/deps.py`, o que quita a dívida da ADR-0007 sem emendá-la. O doctor usa uma única sonda (`GET /better-bibtex/cayw?probe=true`, com `X-Zotero-Version` lido da mesma resposta); o 404 vira "sem Better BibTeX (ou ainda iniciando)". O piso do Better BibTeX, 9.0.65 (commits 051d0843 e 10022a3d), fica em documentação e mensagens, sem checagem de versão.
6. Pandoc: `core/deps.pandoc_path()` (PATH e depois o pandoc do Zettlr.app), a linha `pandoc` no doctor e o piso único 3.8.2, exigido pelas tabelas rotuladas do `crossref.lua` (ADR-0035). Este piso estava implícito na ADR-0035 e fica registrado aqui; a linha `pandoc` do doctor é nova.
7. Emendas:
   - **ADR-0008:** o layout α canônico passa a `{_meta.md, _extract.md}`. `_annotations.md` e `note__*.md` são legado legível; só o `migrate-layout` ainda grava `_annotations.md`.
   - **ADR-0020:** a premissa "reconectar duplicaria o autoexport" é falsa. O BBT guarda um job por caminho, `add` com a mesma coleção só reagenda, e com parâmetros diferentes recusa, a menos que `replace=true`. A Guarda 1 fica, pelo motivo real: não sobrescrever um `.bib` que já tem entradas. `--replace` segue fora, agora com trigger. A versão do Zotero passa a vir do header da sonda do BBT, não da API local. A recomendação de MCP de terceiro passa de `cookjohn/zotero-mcp` a `54yyyu/zotero-mcp`, só em documentação e marcada "não validada". O `getCollection(collection, true)` do BBT continua criando o caminho antes de checar, por isso as guardas anti-fantasma continuam necessárias.
   - **ADR-0026:** sai `paper_sync_all`; 6 tools `paper`, 10 no total.

## Consequências

O export docx deixa de exigir o Zotero aberto, e o Refresh do coautor não quebra mais. A pesquisadora perde três comandos que nunca geraram arquivo e o passo do toggle. "O que eu anotei" passa a depender de uma ferramenta opcional de terceiros, roteada só por texto. O PAR não tem código nem permissão pré-aprovada para ela, e ela nunca entra no `.mcp.json`. A aposentadoria entra na 0.71.0, o evento breaking único junto com a ADR-0038. As correções do docx entram na 0.70.3. Uma rodada de revisão em que o coautor use os botões do Zotero precisa recomeçar do export.
