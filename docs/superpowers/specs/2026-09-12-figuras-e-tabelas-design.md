# Figuras e tabelas numeradas no export — design

- Data: 2026-09-12
- Achado: ROADMAP "Figuras e tabelas" (gatilho "primeira submissão com figura" atingido: o draft piloto do `pj_piloto_questionario` cita Tables 1–3 e Figures 1–2 como texto fixo).
- Decisão registrada em [ADR-0035](../../adr/adr-0035-figuras-e-tabelas-por-filtro-lua.md).

## Problema

`_build_pandoc_cmd` não tem referência cruzada. O docx sai sem "Figura 1"/"Tabela 1" na legenda, e o autor digita o número à mão no texto, que desalinha quando uma tabela muda de lugar. Hoje nenhum `pj_*` usa `{#fig:}`/`{#tbl:}`, e os drafts citam tabelas e figuras como texto fixo.

Restrição dura: `@fig:x` casa com `CITEKEY_RE` e com o parser de citação do Pandoc. Sem tratamento, o citeproc avisa `citation fig:x not found` e `_assert_no_citeproc_missing` derruba o export. `[@fig:x]` entre colchetes ainda seria contado como grupo de citação pelo citemap e quebraria o pareamento I2/I8.

## Alternativas

| Critério | (a) pandoc-crossref | (b) filtro Lua vendorizado | (c) Pandoc 3.x nativo |
|---|---|---|---|
| Atrito de instalação | binário novo, casado com a versão exata do Pandoc; `doctor` teria que checar os dois | zero, vai no wheel como `zotero_live_docx.lua` | zero |
| `@fig:x` virar citekey | resolvido se o filtro rodar antes do `--citeproc` | resolvido, roda antes do `--citeproc` | **não resolve**: `native_numbering` numera legendas, mas `@fig:x` segue indo pro citeproc |
| Legenda no docx | boa (texto) | campo `SEQ` do Word + rótulo localizado | campo `SEQ` do Word |
| Rótulo pt-BR/en-US | via metadado `figureTitle`/`lang` | tabela de 2 idiomas no filtro | só via `lang`, que também troca o locale do CSL no citeproc (muda termos da bibliografia em estilo sem `default-locale`, como `apa.csl`) |

(c) sozinho não resolve referência. (a) resolve tudo, mas cobra um binário a mais, e casar versão com o Pandoc do Homebrew é exatamente a fricção que o pesquisador no Desktop/Cowork não tem como diagnosticar (Princípio VIII). Escolha: **(b)**, com a mesma sintaxe do pandoc-crossref, o que deixa a porta aberta para migrar sem reescrever drafts.

## Decisão

- `_filters/crossref.lua` entra no comando **antes** de `--citeproc`, em todos os formatos.
- Passo 1: numera, em ordem de documento, todo `Figure` e toda `Table` com legenda. No docx, prefixa a legenda com rótulo + campo `SEQ Figure`/`SEQ Table` (o Word atualiza e lista em "Índice de ilustrações"). No html, com texto `Figura 1: `. No typst, não prefixa, porque o `#figure` do Typst já numera.
- Passo 2: troca cada `Cite` com um único `@fig:x`/`@tbl:x` narrativo por `Figura 1` (espaço inseparável). `@fig:x [@key]`, que o Pandoc funde num `Cite` só, é separado: a citação real segue para o citeproc. Alvo inexistente ou referência dentro de colchetes falha o export com a correção na mensagem.
- Rótulo: `lang` do frontmatter, senão `[writing].language` do projeto (passado como `--metadata=prumo_lang:`). O builder não injeta `lang`, então o locale do citeproc fica como está.
- Sem binário novo: `doctor` não muda. Citemap, `core/citations` e as guardas de conservação não mudam.

## Sintaxe (documentada no modo `write manuscript`)

`![Legenda](figures/x.png){#fig:x}`, `: Legenda {#tbl:x}` sob a tabela, e `@fig:x`/`@tbl:x` solto no texto.

## Aceite

- Teste do builder: `crossref.lua` antes de `--citeproc` em todo formato; `prumo_lang` propagado.
- Teste com pandoc real (pulado sem pandoc no PATH, como o CI): docx com `SEQ Figure`/`SEQ Table`, legenda "Figure 1", texto "Table 1" resolvido e campo `ZOTERO_ITEM` de uma citação viva no mesmo documento, sem aviso de citekey ausente; `[@fig:x]` e alvo inexistente falham.
- Suíte de conservação de citações intocada e verde.
