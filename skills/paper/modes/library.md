---
name: library
description: "Gerencia o acervo bibliográfico do pj_* (docs/references/): sincroniza .bib do Zotero/BBT, atualiza grafo de citação passivo, marca paper principal, lista bibliografia, busca por palavra-chave, vê quem cita quem, audita consistência .bib↔notas."
argument-hint: "[sync | sync-annotations | sync-notes | sync-all | update-cites | set-primary <citekey> | list | graph <citekey> | sync-bib | find <query> | connect <coleção>]"
allowed-tools: Read Write Edit Glob Grep Bash(prumo paper *) Bash(rg *)
prumo:
  version: 1.0.0
  determinism: deterministic
  agent_compat: [claude-code]
  cost_estimate: ~1-3k tokens
  inputs:
    operation: required (sync | sync-annotations | sync-notes | sync-all | update-cites | set-primary | list | graph | sync-bib | find | connect)
    args: optional (operation-specific)
  requires: [cli, zotero]
  phrases:
    - "sincroniza minha bibliografia"
    - "importa minhas anotações do Zotero"
    - "encontra paper sobre Y"
    - "quem cita Z"
    - "marca o paper principal"
    - "liga o projeto à coleção do Zotero"
  legacy: [paper-manager]
---

# Paper Manager — acervo bibliográfico de `pj_*/docs/references/`

<!-- prumo:preflight:begin -->
> **Preflight (contrato ADR-0019) — execute ANTES de qualquer operação desta skill:**
>
> 1. **CLI:** rode `prumo --version`. Se o comando NÃO existir: não simule NENHUMA
>    operação desta skill; roteie para `/par:start` (instalação guiada com
>    consentimento) e pare aqui.
> 2. **Estrutura:** se o diretório não tiver `docs/references/` de um `pj_*`,
>    oriente `prumo init pj_<nome>` — NUNCA crie o scaffold manualmente (o agente
>    não simula trabalho do CLI) e NUNCA cite tooling do monorepo do autor.
> 3. **Zotero:** confira `prumo doctor --json` → `external_deps[name=zotero].present`;
>    ausente/fechado → recuse operações que dependem dele citando o hint do doctor
>    (abrir o Zotero; instalar Better BibTeX).
>
> Recusar-se a operar sem dependência NÃO é falha — é o contrato fail-closed (D1):
> operação exata nunca é simulada.
<!-- prumo:preflight:end -->

Skill para manter o acervo de papers como motor file-based: 1 `.md` por paper, 1 BibTeX central, PDFs em `pdfs/` (gitignored). Todas as operações são feitas via `WebFetch` + `Read`/`Edit`/`Write` — sem novas deps Python.

Pressuposto: o diretório corrente é um `pj_*` com a estrutura padrão em `docs/references/`. Se `docs/references/` não existir, orientar `prumo init pj_<nome>` (via /par:start se o CLI não existir) — nunca retrofit manual.

## Layout esperado

```
pj_*/docs/references/
├── .gitignore
├── _index.md
├── _note_template.md            # template base (vai virar _meta.md)
├── _references.bib
├── pdfs/<citekey>.pdf           # gitignored
└── papers/<citekey>/            # 1 PASTA por paper (layout α)
    ├── _meta.md                 # YAML CSL-JSON + body humano
    ├── _extract.md              # callout estruturado (gerado pelo modo `paper extract`)
    ├── _annotations.md          # highlights do Zotero (gerado pelo prumo paper sync-annotations)
    └── note__<itemKey>__<slug>.md  # 1 child note Zotero por arquivo (gerado pelo prumo paper sync-notes)
```

> [!info]
> Layout legado (`notes/<key>.md` plano, na raiz de `references/`) ainda é lido por compatibilidade durante transição. Para migrar: `prumo paper migrate-layout`.

## YAML é a única fonte de verdade

Toda metadata vive no **frontmatter** da nota. Metadata inline no corpo (campo solto,
tabela de propriedades, `key: value` em parágrafo) é proibida em nota versionada — polui
o RAG file-based que o `wiki query` e o `qmd` varrem.

A forma canônica da nota de paper é `docs/references/_note_template.md`, no próprio
projeto: campos, valores permitidos e seções fixas saem de lá, não da sua memória.

## Citation key — Better BibTeX

Formato: `<sobrenomeMinúsculo><ano><primeiraPalavraTítuloMinúscula>` em ASCII puro (sem acentos, sem espaços, sem hífen). Desempate com sufixo `a/b/c` se colidir com nota existente.

Exemplo: autor Smith, 2024, título "Multimodal fusion for breast cancer grading" → `smith2024multimodal`.

Regras:
- Sobrenome do **primeiro autor** em minúsculo ASCII.
- Ano de publicação (issued.date-parts[0][0] no CSL-JSON).
- Primeira palavra "significativa" do título (ignorar `a`, `an`, `the`, `on`, `of`, `and`, `in`).
- Se a nota `papers/<citekey>/_meta.md` já existir, adicionar sufixo: `smith2024multimodala`, `smith2024multimodalb`, etc.

## Operações

> [!note]
> A operação `add <doi>` (fetching CrossRef direto) foi removida. Hoje o Zotero é a fonte única de metadata e PDF. Para adicionar um paper: (1) insira no Zotero (arraste o PDF, cole o DOI, etc.); (2) o Better BibTeX regrava `_references.bib` automaticamente; (3) rode `/par:paper library sync`. Para os PDFs: `prumo paper sync-pdfs`.

### 1. `sync`

Propaga o estado do `_references.bib` (exportado pelo Better BibTeX do Zotero) para `docs/references/papers/<key>/_meta.md` (layout α). Idempotente; pode ser rodado a qualquer momento.

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
   Para extrair conteúdo dos PDFs: /par:paper extract
   ```

4. **Órfãs** (citekey em `papers/` mas ausente do `.bib`) **não são deletadas** automaticamente — é aviso para o usuário renomear no Zotero ou deletar a nota à mão.

### 1b. `sync-annotations`

Importa highlights + comentários do PDF do Zotero pra `docs/references/papers/<key>/_annotations.md` (arquivo dedicado). Read-only Zotero → repo.

```bash
prumo paper sync-annotations <pj_path_absoluto>
```

Requer **Zotero 9 aberto** + Better BibTeX instalado (API local em `http://localhost:23119`). Se o Zotero estiver fechado, o comando falha com mensagem clara (exit code 2).

### 1c. `sync-notes`

Projeta cada **child note** do Zotero (rascunhos de leitura: "ideias da intro", "crítica metodológica") num arquivo próprio `docs/references/papers/<key>/note__<itemKey>__<slug>.md`. Um arquivo por nota; identificador estável é o `itemKey` do Zotero.

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
1. `rg "^role: primary" docs/references/papers/` para achar o `primary` atual.
2. Se existir, editar esse `.md` trocando `role: primary` → `role: supporting`.
3. Editar `papers/<citekey>/_meta.md` trocando `role: supporting` (ou `background`/`replaced`) → `role: primary`.
4. Atualizar a seção "Paper principal" do `_index.md` com a citação `[@<citekey>]` + título + venue + ano.
5. Confirmar ao usuário com diff das mudanças.

### 4. `list`

Lista tabular dos papers do acervo.

Passos:
1. `Glob docs/references/papers/*/_meta.md`.
2. Para cada nota, `Read` e extrair do YAML: `id`, `role`, `status`, `year`, `tldr`, `tags`.
3. Imprimir tabela markdown: `| citekey | role | status | year | tldr |`.

### 5. `graph <citekey>`

Mostra vizinhos do paper no grafo de citações.

Passos:
1. `Read docs/references/papers/<citekey>/_meta.md` → campo `cites: [...]` → lista de quem este paper cita (dentro do acervo).
2. `rg "@<citekey>\b" docs/references/papers/ -l` (gramática Pandoc: `[@k]` e `@k`) + `rg "^\s*-\s*<citekey>\s*$" docs/references/papers/ -l` (campo `cites:`, que o `_NotaDumper` serializa em bloco) → quem cita este paper.

   > O `\b` final evita colisão de prefixo (`@boehm2025multimodal` casaria também
   > `@boehm2025multimodalX`). Citekey Pandoc admite `-`, `.`, `:` e `_`, então
   > `\b` não é infalível — confira a lista antes de reportar.
3. Imprimir duas listas: **cita** (forward) e **citado por** (reverse).
4. Se o paper cita algo que não tem `.md` correspondente, reportar como "paper conhecido mas sem nota — está só no `.bib`".

### 6. `sync-bib`

Audita consistência entre `papers/*/_meta.md` e `_references.bib`.

Passos:
1. Coletar citekeys em `papers/`: `rg "^id: " papers/ -N` → set A.
2. Coletar citekeys em `_references.bib`: `rg "^@\w+\{([^,]+)," _references.bib -o -r '$1'` → set B.
3. Reportar:
   - Notas sem entrada BibTeX: A \ B.
   - Entradas BibTeX sem nota: B \ A (paper conhecido mas sem literature note).
4. Não fazer nada automaticamente — apenas listar. Usuário decide se quer criar a nota (`prumo paper sync`) ou remover a entrada do `.bib`.

### 7. `find <query>`

Fuzzy lookup no acervo por autor + título + ano + tldr. Útil para o usuário obter o citekey rapidamente quando quer citar num notebook/IDE sem abrir o editor.

Passos:

1. Executar:
   ```bash
   prumo paper find "<query>" --path <pj_path_absoluto>
   ```

2. Mostrar o output integral (já vem formatado: citekey, role, status, author, title, year, tldr).

3. Se o usuário estiver claramente querendo inserir uma citação em um arquivo aberto, oferecer proativamente "quer que eu edite o arquivo `<nome>` e insira `[@<citekey>]` na linha <N>?".

### 8. `connect <coleção>`

Liga o `.bib` do projeto a uma coleção do Zotero via `autoexport.add` do Better BibTeX — o comando que substitui o fio manual de configurar "Keep updated" dentro do Zotero. Normalmente é rodado uma única vez, logo depois de `prumo init`.

Quando o usuário pedir algo como "conecta minha coleção X" (ou "liga meu projeto na coleção X do Zotero"):

Passos:

1. **Pré-condição**: Zotero aberto (com Better BibTeX instalado). Se não estiver, o comando falha com mensagem clara e exit code 2 — não insista sem reabrir o Zotero.
2. Executar via `Bash`:
   ```bash
   prumo paper connect "X"
   ```
3. Se o CLI responder que o nome é ambíguo (mesma coleção em mais de uma biblioteca), rodar de novo acrescentando `--library`:
   ```bash
   prumo paper connect "X" --library "<nome da biblioteca>"
   ```
4. Se o CLI responder que a coleção **não existe**, NÃO improvise: mostre as sugestões parecidas que o próprio comando devolveu e pergunte ao usuário se ele quis dizer uma delas **ou** se quer criar a coleção. Só com a resposta dele em mãos vá para o passo 5.
5. **Somente se o usuário pedir a criação em palavras dele** ("cria essa coleção", "ela ainda não existe, pode criar"), rode com `--create`:
   ```bash
   prumo paper connect "X" --create
   ```
   O comando imprime o caminho completo que vai materializar, segmento por segmento, e pede confirmação. Repasse esse eco ao usuário como veio — é a última barreira antes de a coleção nascer de verdade no acervo dele.
6. Em caso de sucesso, sugerir o próximo passo ao usuário:
   ```bash
   prumo paper sync
   ```

Regras duras:

- **NUNCA** criar ou editar `_references.bib` à mão para "ajudar" — o autoexport é responsabilidade exclusiva do Better BibTeX; a skill não simula esse trabalho.
- **NUNCA acrescente `--create` por iniciativa própria**, e **nunca acrescente `--yes`** — em nenhuma circunstância, nem para "resolver" um typo, nem para desatolar um comando que falhou, nem quando a criação parecer obviamente o que o usuário queria. `--create` cria coleção no acervo real do pesquisador e **não tem desfazer pelo CLI** (o Better BibTeX não expõe remoção; limpar é manual na UI do Zotero). A decisão de criar é do humano, com o caminho na frente dos olhos — ver [ADR-0028](../../docs/adr/adr-0028-criacao-de-colecao-opt-in.md), que pelo mesmo motivo mantém a tool MCP `paper_connect` sem esse parâmetro.
- Sem `--create`, typo no nome da coleção **nunca** cria nada no Zotero: o comando valida a existência da coleção antes de qualquer chamada que altere o Zotero, e falha citando sugestões parecidas em vez de criar uma coleção fantasma. Com `--create`, essa rede de proteção passa a ser o eco + a confirmação — mais um motivo para a flag só entrar quando o usuário pediu.
- Se o `_references.bib` do projeto já tiver entradas reais, o comando recusa reconectar (evita duplicar o autoexport já configurado) — oriente o usuário a conferir Preferences → Better BibTeX → Automatic export no Zotero.

## Erros comuns

- **Citekey colide**: adicionar sufixo `a/b/c` automaticamente (ex.: `smith2024multimodal` já existe → `smith2024multimodala`).
- **`docs/references/` não existe**: orientar `mkdir` do layout mínimo + copiar template (ou rodar scaffold em novo projeto).
- **PDF presente mas sem nota**: rodar `prumo paper sync` para gerar a nota a partir da entrada do `.bib`; o campo `pdf:` vai apontar para o arquivo correto.

## Boundaries

- Skill **não** edita o `.gitignore` nem arquivos fora de `docs/references/`.
- Skill **não** faz commits — deixa isso para o usuário (e para `/project-manager` quando for registrar ref no monorepo).
- Skill respeita a rule `.claude/rules/documentation.md`: YAML-only, citekey BBT, seções fixas.
