# pj_<NOME>

## Objetivo
_(1–3 linhas)_

## Hipótese
_(a tese central do estudo)_

## Research Questions
- RQ1:
- RQ2:

## Editor (Zettlr) — setup one-time

O front humano deste projeto é o [Zettlr](https://www.zettlr.com) (≥ 3.0 — o Pandoc embutido precisa ser 3.x). Uma vez só:

1. **Workspace:** File → Open Workspace → raiz deste projeto.
2. **Preview de citação:** Settings → Display → ligar "Render citations".
3. **Autocomplete:** digite `@` — as chaves vêm do `bibliography:` no frontmatter dos drafts (`references/_references.bib`, mantido pelo Better BibTeX com "Keep updated").
4. **Perfil docx de trabalho:** Settings → Assets Manager → defaults files → importar `docs/templates/prumo-docx.yaml`. Produz docx estilizado com campos Zotero vivos — sem URIs de relink e sem guardas: bom para leitura/compartilhamento, NUNCA para entrega.
5. **Docx canônico (entrega/coautores):** Settings → Import/Export → Custom export commands → nome "prumo docx (canônico)", comando `prumo-zettlr-export`. Ou no terminal: `prumo write export docs/drafts/<arquivo>.md`.
6. **Convivência com agentes:** ativar o reload automático de mudanças externas ("Always load remote changes to the current file").
7. Prumo reinstalado e o export do perfil quebrou? `prumo write zettlr-profile` regenera (o `prumo doctor` avisa).

Limitações documentadas: o preview in-editor é sempre Chicago in-text (o CSL real aparece nos exports); com Zotero fechado o preview segue funcionando (lê o `.bib` estático), mas o `.bib` pode estar stale.
