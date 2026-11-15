# ADR-0043 — Painel "Projeto": etapas do estudo calculadas no Python, desenhadas pelo mod

- Status: proposto
- Data: 2026-11-15
- Origem: pedido do mantenedor; spec `docs/superpowers/specs/2026-11-14-painel-de-etapas-do-projeto-design.md`. Substitui o item 3 da ADR-0039

## Contexto

O painel "Revisão do manuscrito" (ADR-0039, item 3) contava as marcas CriticMarkup e lia o `page` do `events.yaml` com regex próprias em TypeScript, repetindo o que `src/par/status.py` já faz com o parser e o schema do domínio (Princípio I). Abria só com `reviews/` no disco, então não guiava quem mais precisa: o projeto recém-criado. Fazia uma conexão e duas chamadas MCP por página a cada turno. O `prumo status` já sabia o próximo passo, numa cadeia fixa que não conhecia protocolo nem entrega, e ninguém o via sem perguntar.

## Decisão

1. **Etapas no Python.** `src/par/status.py` deriva do disco sete etapas: Pergunta, Bibliografia, Leitura, Protocolo (só com o módulo `protocol`; acompanha o SAP e o projeto CEP), Escrita, Revisão (só com `reviews/`) e Entrega (docx pela regra de nome default do `write export`). Cada uma é `done`, `current`, `attention` ou `todo`. A primeira não feita é a atual, e o `next` do status é o dela: CLI, skill `start` e painel concordam por construção.
2. **Schema.** `ProjectStatus/v1` só ganha chaves: `stages`, e `kind`/`framework` na pergunta (Princípio IV).
3. **Tool MCP `project_status(pj_path)`**, só leitura (ADR-0017).
4. **Painel "Projeto"** (`hooks/mods/project.tsx`, comando `/projeto`) no lugar do painel de revisão e do `/revisao`. Uma chamada MCP por atualização (início da sessão, fim de cada turno, botão). Uma linha por etapa e um botão que só preenche o prompt com a frase do próximo passo; a etapa atual vai também para a linha de status. Abre sozinho só dentro de um `pj_*`.
5. **Ordem.** A pergunta do estudo vem antes da bibliografia: em pesquisa em saúde ela orienta a busca.

## Consequências

- O mod não interpreta nada do disco; mudar uma etapa é mudar Python e teste Python.
- A lista de marcas de uma revisão deixa de estar no painel; continua no `review reconcile`, a um prompt de distância.
- O primeiro passo sugerido a projeto novo passa de "conecte a coleção do Zotero" para "feche a pergunta do estudo".
- Esqueletos de módulo em `writing/` deixam de contar como draft; um esqueleto é reconhecido comparando com o template empacotado. Pasta do projeto renomeada depois do `init` faz o esqueleto contar como preenchido.
- Docx exportado com `--out` fora de `build/exports/` não conta para a etapa Entrega.
