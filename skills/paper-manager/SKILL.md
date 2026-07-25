---
name: paper-manager
description: "Gerencia o acervo bibliográfico do pj_* (references/): sincroniza .bib do Zotero/BBT, atualiza grafo de citação passivo, marca paper principal, lista bibliografia, busca por palavra-chave, vê quem cita quem, audita consistência .bib↔notas."
when_to_use: |
  Quando o usuário pedir para sincronizar bibliografia, importar anotações
  ou child notes do Zotero, atualizar grafo, marcar paper principal, listar
  papers, "encontrar paper sobre Y", "quem cita Z", auditar consistência, ou
  mencionar "bibliografia", "paper principal", "referências do projeto",
  "minhas notas do Zotero".
argument-hint: "[sync | sync-annotations | sync-notes | sync-all | update-cites | set-primary <citekey> | list | graph <citekey> | sync-bib | find <query>]"
allowed-tools: Read Write Edit Glob Grep Bash(prumo paper *) Bash(rg *)
prumo:
  version: 1.0.0
  determinism: deterministic
  agent_compat: [claude-code]
  cost_estimate: ~1-3k tokens
  inputs:
    operation: required (sync | sync-annotations | sync-notes | sync-all | update-cites | set-primary | list | graph | sync-bib | find)
    args: optional (operation-specific)
  requires: [cli, zotero]
---

# Paper Manager — acervo bibliográfico de `pj_*/references/`

<!-- prumo:preflight:begin -->
> **Preflight (contrato ADR-0019) — execute ANTES de qualquer operação desta skill:**
>
> 1. **CLI:** rode `prumo --version`. Se o comando NÃO existir: não simule NENHUMA
>    operação desta skill; roteie para `/prumo-assist:start` (instalação guiada com
>    consentimento) e pare aqui.
> 2. **Drift CLI×plugin (evidência da Fase 0):** se `$CLAUDE_PLUGIN_ROOT` estiver
>    definido, compare a versão do CLI com o campo `version` de
>    `$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json`. CLI mais antigo → avise
>    ("CLI X < plugin Y — comandos novos podem não existir") e ofereça
>    `uv tool upgrade prumo-assist` (rode SÓ com consentimento). Sem a variável,
>    pule este passo em silêncio.
> 3. **Estrutura:** se o diretório não tiver `references/` + `docs/` de um `pj_*`,
>    oriente `prumo init pj_<nome>` — NUNCA crie o scaffold manualmente (o agente
>    não simula trabalho do CLI) e NUNCA cite tooling do monorepo do autor.
> 4. **Zotero:** confira `prumo doctor --json` → `external_deps[name=zotero].present`;
>    ausente/fechado → recuse operações que dependem dele citando o hint do doctor
>    (abrir o Zotero; instalar Better BibTeX).
>
> Recusar-se a operar sem dependência NÃO é falha — é o contrato fail-closed (D1):
> operação exata nunca é simulada.
<!-- prumo:preflight:end -->

Skill para manter o acervo de papers como motor file-based: 1 `.md` por paper, 1 BibTeX central, PDFs em `pdfs/` (gitignored). Todas as operações são feitas via `WebFetch` + `Read`/`Edit`/`Write` — sem novas deps Python.

Pressuposto: o diretório corrente é um `pj_*` com a estrutura padrão em `references/`. Se `references/` não existir, orientar `prumo init pj_<nome>` (via /prumo-assist:start se o CLI não existir) — nunca retrofit manual.

## Layout esperado

```
pj_*/references/
├── _index.md
├── _references.bib
├── pdfs/<citekey>.pdf           # gitignored
├── templates/literature_note.md # template base (vai virar _meta.md)
├── views/papers.base
└── notes/<citekey>/             # 1 PASTA por paper (layout α)
    ├── _meta.md                 # YAML CSL-JSON + body humano
    ├── _extract.md              # callout estruturado (gerado pela skill paper-extract)
    ├── _annotations.md          # highlights do Zotero (gerado pelo prumo paper sync-annotations)
    └── note__<itemKey>__<slug>.md  # 1 child note Zotero por arquivo (gerado pelo prumo paper sync-notes)
```

> [!info]
> Layout legado (`notes/<key>.md` plano) ainda é lido por compatibilidade durante transição. Para migrar: `prumo paper migrate-layout`.

## Citation key — Better BibTeX

Formato: `<sobrenomeMinúsculo><ano><primeiraPalavraTítuloMinúscula>` em ASCII puro (sem acentos, sem espaços, sem hífen). Desempate com sufixo `a/b/c` se colidir com nota existente.

Exemplo: autor Smith, 2024, título "Combinado model for risk grading" → `smith2024combinado`.

Regras:
- Sobrenome do **primeiro autor** em minúsculo ASCII.
- Ano de publicação (issued.date-parts[0][0] no CSL-JSON).
- Primeira palavra "significativa" do título (ignorar `a`, `an`, `the`, `on`, `of`, `and`, `in`).
- Se a nota `notes/<citekey>/_meta.md` já existir, adicionar sufixo: `smith2024combinadoa`, `smith2024combinadob`, etc.

## Operações

> [!note]
> A operação `add <doi>` (fetching CrossRef direto) foi removida. Hoje o Zotero é a fonte única de metadata e PDF. Para adicionar um paper: (1) insira no Zotero (arraste o PDF, cole o DOI, etc.); (2) o Better BibTeX regrava `_references.bib` automaticamente; (3) rode `/prumo-assist:paper-manager sync` (ou `make sync-paper`). Para os PDFs: `prumo paper sync-pdfs` (ou `make sync-pdf-paper` que faz os dois).

### 1. `sync`

Propaga o estado do `_references.bib` (exportado pelo Better BibTeX do Zotero) para `references/notes/<key>/_meta.md` (layout α). Idempotente; pode ser rodado a qualquer momento.

Passos:
1. Executar via `Bash`:
   ```bash
   prumo paper sync <pj_path_absoluto>
   ```
   (cwd tipicamente é o próprio `pj_*`, então `<pj_path_absoluto>` é `$PWD`.)

2. Em seguida, sempre rodar `update-cites` (operação 2) — o grafo passivo é parte do contrato de `sync`:
   ```bash
   prumo paper graph <pj_path_absoluto>
   ```

3. Relatar ao usuário:
   ```
   ✓ N notas novas, M atualizadas, K órfãs.
   ✓ Grafo: +X arestas, -Y removidas.
   Para extrair conteúdo dos PDFs: /prumo-assist:paper-extract-all (ou make extract-paper-all)
   ```

4. **Órfãs** (citekey em `notes/` mas ausente do `.bib`) **não são deletadas** automaticamente — é aviso para o usuário renomear no Zotero ou deletar a nota à mão.

### 1b. `sync-annotations`

Importa highlights + comentários do PDF do Zotero pra `references/notes/<key>/_annotations.md` (arquivo dedicado). Read-only Zotero → repo.

```bash
prumo paper sync-annotations <pj_path_absoluto>
```

Requer **Zotero 9 aberto** + Better BibTeX instalado (API local em `http://localhost:23119`). Se o Zotero estiver fechado, o comando falha com mensagem clara (exit code 2).

### 1c. `sync-notes`

Projeta cada **child note** do Zotero (rascunhos de leitura: "ideias da intro", "crítica metodológica") num arquivo próprio `references/notes/<key>/note__<itemKey>__<slug>.md`. Um arquivo por nota; identificador estável é o `itemKey` do Zotero.

```bash
prumo paper sync-notes <pj_path_absoluto>
```

Read-only Zotero → repo. Edição da nota acontece **no Zotero**; o repo é espelho navegável. Texto humano escrito **após** o bloco `<!-- END ZOTERO -->` é preservado entre syncs. Requer Zotero aberto (mesmo pré-requisito do `sync-annotations`).

### 1d. `sync-all`

Atalho ergonômico: roda `sync` + `sync-annotations` + `sync-notes` em sequência.

```bash
prumo paper sync-all <pj_path_absoluto>
```

`sync` roda offline (lê o `.bib`). As fases que precisam do Zotero são **puladas com aviso** se ele estiver fechado — o comando não falha por isso. Use este como o comando padrão pós-leitura.

### 2. `update-cites`

Invocar separadamente se o usuário quiser re-rodar só o grafo (ex.: acabou de escrever wikilinks novos). Idempotente; zero custo.

```bash
prumo paper graph <pj_path_absoluto>
```

### 3. `set-primary <citekey>`

Marca um paper como `role: primary` (apenas 1 por projeto).

Passos:
1. `rg "^role: primary" references/notes/` para achar o `primary` atual.
2. Se existir, editar esse `.md` trocando `role: primary` → `role: supporting`.
3. Editar `notes/<citekey>/_meta.md` trocando `role: supporting` (ou `background`/`replaced`) → `role: primary`.
4. Atualizar a seção "Paper principal" do `_index.md` com a citação `[@<citekey>]` + título + venue + ano.
5. Confirmar ao usuário com diff das mudanças.

### 4. `list`

Lista tabular dos papers do acervo.

Passos:
1. `Glob references/notes/*/_meta.md`.
2. Para cada nota, `Read` e extrair do YAML: `id`, `role`, `status`, `year`, `tldr`, `tags`.
3. Imprimir tabela markdown: `| citekey | role | status | year | tldr |`.
4. Lembrar: no Obsidian a view `references/views/papers.base` já mostra isso com filtros interativos.

### 5. `graph <citekey>`

Mostra vizinhos do paper no grafo de citações.

Passos:
1. `Read references/notes/<citekey>/_meta.md` → campo `cites: [...]` → lista de quem este paper cita (dentro do acervo).
2. `rg "\[\[@<citekey>\]\]" references/notes/ -l` + `rg "cites:.*<citekey>" references/notes/ -l` → quem cita este paper.
3. Imprimir duas listas: **cita** (forward) e **citado por** (reverse).
4. Se o paper cita algo que não tem `.md` correspondente, reportar como "paper conhecido mas sem nota — está só no `.bib`".

### 6. `sync-bib`

Audita consistência entre `notes/*/_meta.md` e `_references.bib`.

Passos:
1. Coletar citekeys em `notes/`: `rg "^id: " notes/ -N` → set A.
2. Coletar citekeys em `_references.bib`: `rg "^@\w+\{([^,]+)," _references.bib -o -r '$1'` → set B.
3. Reportar:
   - Notas sem entrada BibTeX: A \ B.
   - Entradas BibTeX sem nota: B \ A (paper conhecido mas sem literature note).
4. Não fazer nada automaticamente — apenas listar. Usuário decide se quer criar a nota manualmente (ou via Zotero Integration no Obsidian) ou remover a entrada do `.bib`.

### 7. `find <query>`

Fuzzy lookup no acervo por autor + título + ano + tldr. Útil para o usuário obter o citekey rapidamente quando quer citar num notebook/IDE sem abrir o Obsidian.

Passos:

1. Executar:
   ```bash
   prumo paper find "<query>" --path <pj_path_absoluto>
   ```

2. Mostrar o output integral (já vem formatado: citekey, role, status, author, title, year, tldr).

3. Se o usuário estiver claramente querendo inserir uma citação em um arquivo aberto, oferecer proativamente "quer que eu edite o arquivo `<nome>` e insira `[@<citekey>]` na linha <N>?".

## Erros comuns

- **Citekey colide**: adicionar sufixo `a/b/c` automaticamente (ex.: `smith2024combinado` já existe → `smith2024combinadoa`).
- **`references/` não existe**: orientar `mkdir` do layout mínimo + copiar template (ou rodar scaffold em novo projeto).
- **PDF presente mas sem nota**: usar o plugin Zotero Integration no Obsidian para gerar a nota a partir da entrada Zotero correspondente; o campo `pdf:` vai apontar para o arquivo correto.

## Boundaries

- Skill **não** edita o `.gitignore`, `.obsidian/`, nem arquivos fora de `references/`.
- Skill **não** faz commits — deixa isso para o usuário (e para `/project-manager` quando for registrar ref no monorepo).
- Skill respeita a rule `.claude/rules/documentation.md`: YAML-only, citekey BBT, seções fixas.
