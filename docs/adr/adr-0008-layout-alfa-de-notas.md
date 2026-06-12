# ADR-0008 — Layout α para notas de referência

- Status: aceito
- Data: 2026-06-11
- Origem: [[2026-05-03-zotero-notes-integration-design]] (pré-existente; formalizado nesta data)

## Contexto
O layout flat (`references/notes/<citekey>.md`) não comporta múltiplos artefatos por paper (metadata, extração, anotações, notas-filhas do Zotero) sem conflito de ownership humano/máquina.

## Decisão
Cada citekey vira pasta: `references/notes/<citekey>/{_meta.md, _extract.md, _annotations.md, note__<itemKey>__<slug>.md}`. `core/note_paths.py` é a única autoridade de caminhos; o layout flat legado continua legível durante a transição; `prumo paper migrate-layout` converte preservando histórico via `git mv`.

## Consequências
Todo código novo usa `note_paths`; lugares que ainda globam o layout flat (ex.: `wiki/stats.py`) são dívida conhecida. O merge de YAML em `paper/sync.py` define ownership por campo (metadata = máquina, curadoria = humano).
