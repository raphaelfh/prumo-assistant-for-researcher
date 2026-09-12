# ADR-0034 — Figuras e tabelas numeradas por filtro Lua vendorizado

- Status: aceito
- Data: 2026-09-12
- Origem: [[2026-09-12-figuras-e-tabelas-design]]. Achado "Figuras e tabelas" do ROADMAP.

## Contexto

O export não numera figuras nem tabelas e não resolve referência cruzada. A primeira submissão com figura chegou com "Table 1" e "Figure 2" digitados à mão. `@fig:x` tem a forma de uma citekey: o Pandoc o parseia como `Cite`, o citeproc avisa citekey ausente e `_assert_no_citeproc_missing` derruba o export.

Três caminhos: pandoc-crossref (binário externo casado com a versão do Pandoc), filtro Lua vendorizado, ou o `native_numbering` do Pandoc 3.x. O nativo numera legendas mas não resolve `@fig:x`, e só localiza o rótulo via `lang`, que também troca o locale do CSL.

## Decisão

Um filtro Lua vendorizado, `_filters/crossref.lua`, com a sintaxe do pandoc-crossref (`{#fig:x}`, `{#tbl:x}`, `@fig:x`, `@tbl:x`). Ele roda antes de `--citeproc` em todo formato, então nenhuma referência chega ao citeproc nem ao filtro Zotero. No docx, a legenda recebe um campo `SEQ` do Word. O rótulo vem do `lang` do frontmatter, senão de `[writing].language`. Referência entre colchetes, ou sem alvo, falha o export com a correção na mensagem, porque `[@fig:x]` seria contado como citação pelo citemap.

## Consequências

Nenhum binário novo: `prumo doctor` não muda. A conservação de citações não muda. O número no texto é estático no docx: se o coautor reordenar figuras no Word, o `SEQ` da legenda atualiza e a menção no texto não. A correção é re-exportar do Markdown. Idioma novo de rótulo é uma linha na tabela do filtro. Migrar para pandoc-crossref não exige reescrever drafts.
