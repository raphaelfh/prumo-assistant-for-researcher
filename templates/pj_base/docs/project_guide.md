# pj_<NOME>

## Objetivo
_(1–3 linhas)_

## Hipótese
_(a tese central do estudo)_

## Research Questions
- RQ1:
- RQ2:

## Escopo do wiki
- **Entidades principais** (datasets, ferramentas, instituições):
- **Conceitos centrais** (métodos, abordagens):
- **Decisões já tomadas** (viram ADR em `docs/studies/<slug>/decisions/`):

## Editor (Zettlr) — setup one-time

O front humano deste projeto é o [Zettlr](https://www.zettlr.com) (recente: o 4.8 traz o pandoc 3.10.1; o export do PAR precisa de pandoc 3.8.2 ou mais novo, confira com `prumo doctor`). Uma vez só:

1. **Workspace:** File → Open Workspace → raiz deste projeto.
2. **Preview de citação:** Settings → Display → ligar "Render citations".
3. **Autocomplete:** digite `@` — as chaves vêm do `bibliography:` no frontmatter dos drafts (`docs/references/_references.bib`, mantido pelo Better BibTeX; o vínculo é feito por `prumo paper connect`).
4. **Perfil docx de trabalho:** peça 'gera o perfil do Zettlr' (roda `prumo write zettlr-profile`) e importe: Settings → Assets Manager → defaults files → importar `docs/templates/prumo-docx.yaml`. Produz docx estilizado com campos Zotero vivos — sem URIs de relink e sem guardas: bom para leitura/compartilhamento, NUNCA para entrega. Para entrega e coautores, peça ao Claude: 'exporta o docx canônico de `<arquivo>`'.
5. **Convivência com agentes:** ativar o reload automático de mudanças externas ("Always load remote changes to the current file").
6. Atualizou o PAR e o `prumo doctor` avisou do perfil? Peça 'regenera o perfil do Zettlr'; não precisa reimportar.

Limitações documentadas: o preview in-editor é sempre Chicago in-text (o CSL real aparece nos exports); com Zotero fechado o preview segue funcionando (lê o `.bib` estático), mas o `.bib` pode estar stale.
