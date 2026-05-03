---
title: Contextos de necessidade → ações no prumo-assist
tags: [journey, playbook]
---

# Contextos de necessidade → ações

> Mapa de bolso: dado um *gatilho* da rotina do pesquisador, qual sequência de comandos do prumo-assist resolve. Organizado pelas 3 fases da [[journey|jornada]].

## Fase 0 · Setup do projeto

### "Estou começando um pj_* novo"
1. `prumo init pj_<nome>` — copia o template e instala skills no `.claude/`.
2. `prumo doctor pj_<nome>` — confere estrutura e integrations.
3. Preencher `.claude/rules/project_context.md` (coorte, labels, ética). 

### "Quero ver se um pj_* antigo ainda está saudável"
1. `prumo doctor` — sinaliza diretórios faltando, integrations quebradas.
2. `prumo paper lint` — bib ↔ notas ↔ pdfs.
3. `prumo wiki lint` — citekeys quebradas, órfãs, frontmatter.

---

## Fase 1 · Pergunta  *(Discover + Define)*

### "Tópico novo, não sei o que já li"
1. `/prumo-assist:wiki-query` — pergunta livre, retorna síntese com citações.
2. `prumo paper find "<keyword>"` — fuzzy lookup no acervo.
3. Decidir: arquivar a resposta em `findings/` ou abrir nova pergunta.

### "Achei um paper que parece relevante"
1. `prumo capture <doi|arxiv|url>` — classifica o input.
2. `/prumo-assist:wiki-ingest <link>` — adiciona ao wiki (delega papers ao paper-manager).
3. Voltar pra `wiki-query` se precisar contextualizar.

### "Preciso fechar um PICOT antes de prosseguir"
1. `/prumo-assist:wiki-query "qual o PICOT atual do estudo?"` — varredura no que já está escrito.
2. Editar `docs/protocol.md` à mão.
3. Registrar a decisão em `docs/decisions/` (ADR curto).

---

## Fase 2 · Evidência  *(Develop)*

### "Quero extrair conteúdo estruturado de um PDF"
1. `/prumo-assist:paper-extract @<citekey>` — preenche callout (TL;DR + PICOT + Método + Resultados + Limitações).
2. Conferir em `references/notes/<citekey>.md`.
3. `prumo paper graph` — atualiza arestas `[[@key]]` no YAML.

### "Importei N papers novos no Zotero"
1. `prumo paper sync` — `.bib` → notas em `references/notes/`.
2. `prumo paper sync-pdfs` — symlinks pra `~/Zotero/storage/`.
3. `prumo paper sync-annotations` — annotations + child notes via API local.
4. `/prumo-assist:paper-extract --batch` quando quiser callouts em massa.

### "Quero navegar pelas conexões do meu acervo"
1. `prumo paper graph` — popula `cites:` no YAML de cada nota.
2. Abrir o grafo do Obsidian (`Ctrl/Cmd + G`).
3. `prumo paper find "<seed>"` quando o grafo for grande demais.

### "Suspeito que o wiki está degradando"
1. `/prumo-assist:wiki-lint` — citekeys quebradas, páginas órfãs, contradições, stale claims.
2. Resolver erros críticos antes de PR.
3. `prumo wiki stats` — sanidade quantitativa por tipo.

---

## Fase 3 · Escrita  *(Deliver)*

### "Vou começar um draft"
1. Criar `.md` em `docs/findings/` ou `docs/sources/` com frontmatter.
2. Escrever — usando `[[@key]]` pra citações inline.
3. `/prumo-assist:scientific-writing` — passe editorial (pontuação, citação, superlativos).

### "Terminei um draft e quero auto-revisar antes de mostrar"
1. `/prumo-assist:scientific-writing` — limpa pontuação e estilo.
2. `/prumo-assist:peer-review` — força/fraqueza/claims sem evidência.
3. Iterar até que o peer-review pare de devolver achados críticos.

### "Preciso exportar pro venue (DOCX/PDF)"
1. `prumo write list-styles` — confirma o CSL do venue.
2. `prumo write export draft.md --to docx --style <venue>` (ou `pdf`/`typst`/`html`).
3. Conferir bibliografia gerada antes de submeter.

### "Tenho um capítulo composto por várias páginas"
1. Criar `index.idx.md` com `pages: [...]` no frontmatter.
2. `prumo write compose --index index.idx.md --to docx`.

### "Recebi o .docx revisado pelo orientador / revisor"
1. `prumo write extract-comments revisado.docx` — checklist Markdown em `docs/comments/`.
2. Endereçar item por item; commitar a cada lote.
3. Repetir o ciclo `scientific-writing` → `peer-review`.

---

## Apoio teórico (qualquer fase)

### "Estou patinando num conceito de estatística/ML"
- Agent `ml-theory-expert` — fundamentação teórica com citações do próprio acervo.

### "Não sei como funciona uma lib da stack"
- Agent `stack-docs-researcher` — consulta documentação atualizada (scikit-learn, Lightning, albumentations, ...).

---

## Quando o gap não tem ferramenta

Se você bateu num gap real (precisa de algo que `prumo` não cobre) e está prestes a fazer um workaround manual, abra uma issue. É candidato a skill nova — segue o princípio I do [[constitution|constitution]].
