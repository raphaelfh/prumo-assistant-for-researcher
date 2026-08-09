# ADR-0023 — Finding como `type: finding` em `notes/`, não diretório próprio

- Status: aceito
- Data: 2026-08-09
- Origem: [[2026-08-08-layout-por-escopo-design]]; substitui [ADR-0014](adr-0014-findings-canonico.md)

## Contexto
ADR-0014 fixou `docs/wiki/findings/` (preferido) com fallback `docs/findings/` como caminho
canônico de finding — um resolver condicional a se `docs/wiki/` existe ou não no projeto.
O layout por escopo (ADR-0022) elimina esse dualismo: `docs/` é a raiz única de leitura, e a
unidade de organização vira o escopo (`docs/studies/<slug>/`), não mais um `docs/wiki/`
opcional. Manter `findings/` como diretório próprio duplicaria taxonomia sem necessidade — um
finding é, na prática, uma nota como outra qualquer, distinguida só pelo que ela afirma sobre
um resultado que valeu arquivar.

## Decisão
Finding deixa de ser diretório. É uma nota comum de `docs/studies/<slug>/notes/` com
`type: finding` no frontmatter YAML (`id`, `type`, `title`, `added`, `status`, `generator`,
`tags`, `sources`). `domains/wiki/findings.py::archive_as_finding` cria/atualiza
`<escopo>/notes/<slug>.md` e mantém `_index.md`/`_log.md` do projeto. Não existe mais resolver
de preferência/fallback — `notes/` sempre existe (é um dos três `SCOPE_DIRS` fixos de todo
escopo, ADR-0022), então não há mais condição "projeto sem `docs/wiki/`" a distinguir.

## Consequências
ADR-0014 fica substituído; o resolver por preferência/fallback que ele registrava não existe
mais no código nem na prosa das skills. Toda skill que oferecia arquivar finding em
`docs/wiki/findings/` (ou fallback `docs/findings/`) passa a oferecer `docs/studies/<slug>/notes/`
com `type: finding`. `wiki-lint` passa a identificar finding por frontmatter (`type: finding`),
não por diretório — inclusive a checagem de `status: superseded` sem cross-ref.
