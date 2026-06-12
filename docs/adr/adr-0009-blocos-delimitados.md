# ADR-0009 — Blocos delimitados HTML-comment como contrato humano/máquina

- Status: aceito
- Data: 2026-06-11
- Origem: padrão transversal em `paper/callout.py`, `protocol/propagate.py`, `write/compose.py`, `paper/zotero.py` (pré-existente; formalizado nesta data)

## Contexto
Artefatos Markdown são editados por humanos E regenerados por máquina. Sem fronteira explícita, cada regeneração destruiria curadoria humana.

## Decisão
Toda região machine-owned dentro de Markdown humano é delimitada por comentários HTML pareados (`<!-- x:begin ... -->` / `<!-- x:end -->`), opcionalmente com hash/versão no marcador para detectar staleness (`picot:begin v=N hash=sha8`). A máquina só reescreve dentro do bloco; o humano só escreve fora.

## Consequências
Regeneração idempotente e diffs limpos. O padrão se estende aos índices gerados deste repo (`prumo:skills-table`, `prumo:kb-index` etc. via `gen_indexes.py`). Delimitador corrompido é erro reportável, nunca "best effort".
