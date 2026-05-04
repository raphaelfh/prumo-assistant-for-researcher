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

### "Tópico novo — preciso mapeamento de literatura amplo *antes* de fechar pergunta"
*Busca exploratória pré-PICOT. Objetivo: ver o terreno.*
1. `/prumo-assist:wiki-query` — pergunta livre, retorna síntese com citações do que já existe no acervo.
2. `prumo paper find "<keyword>"` — fuzzy lookup, ver o que está perto.
3. Agente `ml-theory-expert` — pra fundamentação teórica do tema.
4. Capturar achados como rascunhos em `docs/brainstorm/daily/<data>.md` (se módulo `brainstorm-pipeline` ativado).

### "Achei um paper que parece relevante"
1. `prumo capture <doi|arxiv|url>` — classifica o input.
2. `/prumo-assist:wiki-ingest <link>` — adiciona ao wiki (delega papers ao paper-manager).
3. Voltar pra `wiki-query` se precisar contextualizar.

### "Preciso fechar um PICOT antes de prosseguir"
*Pivô da Fase 1: da busca ampla → busca focada.*
1. `/prumo-assist:wiki-query "qual o PICOT atual do estudo?"` — varredura no que já está escrito.
2. Editar `docs/protocol.md` (operacional clínico) e `docs/project.md` (texto formal) à mão.
3. Registrar a decisão em `docs/decisions/` (ADR curto explicando o porquê).

### "PICOT fechado — agora preciso busca focada e cumulativa"
*Busca dirigida pós-PICOT. Objetivo: literatura robusta sobre o escopo definido.*
1. Lista de DOIs do PICOT em mãos.
2. `/prumo-assist:wiki-ingest <DOI>` em batch — um por vez ou em lote.
3. `/prumo-assist:paper-extract --batch` — gera callouts estruturados de todos.
4. `prumo paper graph` — popula `cites:` no YAML; vê quem cita quem.
5. `/prumo-assist:wiki-lint` — confirma que o acervo está internamente consistente.

---

## Fase 2 · Evidência  *(Study and Develop)*

### "Quero extrair conteúdo estruturado de um PDF"
1. `/prumo-assist:paper-extract @<citekey>` — preenche callout (TL;DR + PICOT + Método + Resultados + Limitações).
2. Conferir em `references/notes/<citekey>/_extract.md` *(layout α)*.
3. `prumo paper graph` — atualiza arestas `[[@key]]` no YAML.

### "Importei N papers novos no Zotero"
1. `prumo paper sync` — `.bib` → `references/notes/<key>/_meta.md` *(layout α)*.
2. `prumo paper sync-pdfs` — symlinks pra `~/Zotero/storage/`.
3. `prumo paper sync-annotations` — highlights → `_annotations.md`.
4. `prumo paper sync-notes` — child notes Zotero → `note__*.md` *(novo, spec B1)*.
5. `/prumo-assist:paper-extract --batch` quando quiser callouts em massa.
6. `prumo paper sync-all` faz 1–4 em sequência *(orquestrador, novo)*.

### "Vou ler um paper a fundo agora — leitura ativa estruturada"
*Sub-fluxo dentro da fase de Estudo.*
1. Abrir o PDF no Zotero (com PDF reader integrado).
2. Highlights coloridos por categoria (amarelo = importante; rosa = crítica; verde = método; azul = quote).
3. **Child notes** no Zotero pra ideias longas (1 ideia = 1 child note); título descritivo.
4. Ao terminar a sessão: `prumo paper sync-annotations` + `prumo paper sync-notes` puxam tudo pro repo.
5. Conferir em `references/notes/<key>/_annotations.md` e `note__*.md`.

### "Quero estudar conceito X usando minhas próprias fontes"
*Claude como tutor metacognitivo. Sessão Socrática em 5 steps ancorada no acervo.*
1. `/prumo-assist:active-learning <topic>` — skill conduz: Recall → Anchor → Connect → Apply → Reflect.
2. Skill cria log em `docs/wiki/study-sessions/<topic>-<data>.md`.
3. No step Reflect, skill oferece arquivar insight como finding.
4. Citação strict — só citekeys do acervo. Refs faltantes viram `[REF FALTANTE]`.

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
1. Criar `.md` em `docs/findings/` ou `docs/sources/` com frontmatter (ou editar `docs/project.md` direto).
2. Escrever — usando `[[@key]]` pra citações inline.
3. `/prumo-assist:scientific-writing` — passe editorial (pontuação, citação, superlativos).

### "Terminei um draft e quero auto-revisar antes do orientador"
1. `/prumo-assist:scientific-writing` — limpa pontuação e estilo.
2. `/prumo-assist:peer-review` — força/fraqueza/claims sem evidência.
3. Iterar até que o peer-review pare de devolver achados críticos.

### "Vou submeter pro CEP / Comitê de Ética em Pesquisa"
*Documento brasileiro com estrutura específica (Plataforma Brasil, TCLE, riscos/benefícios).*
1. *Skill futura* `/prumo-assist:write-projeto-cep` — usa `_extract.md` e `note__*.md` pra estruturar — em backlog *(spec separada)*.
2. Hoje: editar à mão usando `docs/project.md` como base; consultar `_extract.md` dos papers pra metodologia ancorada.
3. `prumo write export <doc>.md --to docx` pra entregar formatado.

### "Vou montar artigo pra venue (NEJM/Lancet/Nature Med/...)"
1. *Skill futura* `/prumo-assist:write-paper` — IMRaD venue-aware — em backlog.
2. Hoje: `prumo write list-styles` confirma o CSL do venue.
3. `prumo write export draft.md --to docx --style <venue>` (ou `pdf`/`typst`/`html`).
4. Conferir bibliografia gerada antes de submeter.

### "Vou escrever a seção de métodos estatísticos"
1. *Skill futura* `/prumo-assist:write-statistics` — plano de análise estatística + sample-size + métodos — em backlog.
2. Hoje: agente `ml-theory-expert` ajuda a fundamentar; `_extract.md` dos papers traz a base ancorada.

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
