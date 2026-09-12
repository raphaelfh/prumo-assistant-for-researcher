---
title: Recálculo determinístico das estatísticas relatadas no `prumo wiki lint`
date: 2026-09-12
status: approved
tags: [wiki, lint, review, statistics, deterministic]
---

# Recálculo determinístico das estatísticas relatadas no `prumo wiki lint`

## Problema

No A/B de 2026-09-12 (`review critique` do prumo vs ARS), só a cadeira metodológica do ARS
recalculou os IC de Wilson, as porcentagens e os 148 valores q de Benjamini-Hochberg do
manuscrito. O prumo não recalculou nada — e isso é aritmética, não julgamento: um LLM gasta
token para fazer o que 30 linhas de Python fazem de forma reprodutível (Princípio II).

## Decisão

Um código novo em `prumo wiki lint`: `stat_mismatch` (severity `warning`), um por página,
emitido **só** quando há divergência. A mensagem lista cada divergência com o valor relatado e
o recalculado. Lógica em `domains/wiki/stats_check.py` (stdlib: `statistics.NormalDist`);
`lint.py` ganha uma chamada no laço de páginas do escopo.

Padrões reconhecidos (nada além do que o draft real usa — Princípio VI):

1. `x of n (p%)` / `x of n, p%` (aceita `de` e uma palavra entre `n` e o valor): `p` contra
   `100·x/n`, tolerância de meia unidade na precisão relatada.
2. `x of n (p%, 95% CI a to b)`: IC de Wilson (z = 1,96), tolerância de uma unidade na
   precisão relatada.
3. Tabela Markdown com exatamente uma coluna `p…` e uma ou mais colunas `q…` (coluna
   `Família` opcional): q de BH recalculado por família (a tabela, ou o valor da coluna
   família). Coluna `q` cujo cabeçalho contém `global` é agrupada com as homônimas de todas as
   tabelas da página. O arredondamento do p exibido é absorvido por limites: BH é monótono em
   cada p, então q recalculado com todos os p em `p − ½unidade` e em `p + ½unidade` cerca o
   valor verdadeiro; o q relatado passa se cair nesse intervalo ± meia unidade.

Qualquer coisa que não parse (sem `n`, `<0,001`, IC em outro formato) é pulada em silêncio,
nunca adivinhada. Tabela com uma célula p/q não numérica é pulada inteira (o `m` ficaria errado).

Suposição documentada: a tabela contém a família inteira. Um recorte parcial gera falso
positivo — é o custo de não adivinhar `m`.

## Alternativas rejeitadas

- **Subcomando novo (`prumo write check-stats`)**: mais um conceito para o pesquisador
  (Princípio VIII); o lint já varre `writing/` e é o que `review critique` manda rodar.
- **Deixar para o `reviewer` (LLM)**: não reprodutível e caro; o ARS precisou de uma cadeira
  inteira para isso.
- **scipy/statsmodels**: dependência nova para duas fórmulas de poucas linhas.
- **Emitir `info` com o total conferido**: ruído; só divergência vira issue.

## Aceitação

- Draft real (`paper-piloto-submission.md`) e `material_suplementar_piloto.md`:
  zero `stat_mismatch`.
- Fixture sintética com IC errado e q errado: um `stat_mismatch` citando os dois pares
  relatado/recalculado.
- Padrões não parseáveis não geram issue.
