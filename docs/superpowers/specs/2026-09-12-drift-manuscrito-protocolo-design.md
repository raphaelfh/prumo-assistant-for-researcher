# Drift do manuscrito contra protocolo e PICOT — design

## Problema

No A/B de 2026-09-12 (`review critique` vs ARS), três contradições reais entre o
manuscrito e o `writing/protocol.md` só apareceram porque o revisor leu o protocolo
por acaso: janela de coleta (março–julho vs março–agosto de 2023), subgrupos
"não pré-especificados" vs estratificações pré-declaradas, e testes nomeados no
protocolo (qui-quadrado, Cochran–Armitage) ausentes no manuscrito. São fatos
extraíveis sem LLM (Princípio II).

## Decisão

- Módulo `domains/protocol/drift.py` (funções puras): extrai de cada linha fatos de
  vocabulário fechado, bilíngue pt/en — janelas de datas (mês a mês de ano), `n=N`,
  testes estatísticos nomeados (≈10 canônicos) e afirmações de pré-especificação de
  subgrupo/estratificação (polaridade sim/não).
- Lado protocolo = `.claude/picot.toml` (texto bruto, via `picot_path`) + `protocol.md`
  do escopo; a localização preferida é `protocol.md`.
- Comparação, cada drift reportado uma vez com `arquivo:linha` dos dois lados e dica
  pt-BR: janela do draft fora das janelas do protocolo; `n` do protocolo cujo número
  não aparece no draft; teste só de um lado (só se ambos nomeiam algum teste);
  polaridade de pré-especificação oposta.
- Superfície: **`prumo protocol diff`** ganha a chave `drift` no JSON e linhas no
  relatório humano. Sem flag nova: o argumento `path` já existente, quando aponta
  para um `.md`, restringe a esse draft; senão, todos os `writing/*.md` exceto
  `protocol.md`. Nunca escreve no manuscrito.

## Alternativas rejeitadas

- Subcomando novo (`protocol drift`): mais um conceito (Princípio VIII); o `diff` já é
  onde o pesquisador olha "o que divergiu da PICOT".
- Flag `--draft`: o `path` posicional já absorve.
- Pedir ao `reviewer` que leia sempre o protocolo: agêntico e não auditável (II).
- Lógica em `write`/`review`: domínios não se importam; leitura da PICOT fica em
  `protocol` (I).
- NLP/parsing de números por extenso: fora do vocabulário fechado (VI).

## Aceitação

- Fixture com excertos do projeto real: as três contradições detectadas.
- Textos concordantes: nenhum drift.
- `protocol diff` sem `picot.toml` ainda reporta drift a partir de `protocol.md`.
