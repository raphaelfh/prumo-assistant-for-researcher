# ADR-0007 — Zotero/BBT via stdlib urllib, endpoint 127.0.0.1:23119

- Status: aceito
- Data: 2026-06-11
- Origem: docstrings de `domains/paper/zotero.py` (pré-existente; formalizado nesta data)

## Contexto
A integração Zotero usa a API local do Better BibTeX. Adicionar `requests`/`httpx` traria uma dependência inteira para meia dúzia de chamadas HTTP locais.

## Decisão
Todas as chamadas Zotero/BBT usam `urllib` da stdlib. O endpoint default é `http://127.0.0.1:23119` (IP literal, não `localhost`, para evitar surpresas de resolução IPv6), com override via env `PRUMO_ZOTERO_BASE`.

## Consequências
Helpers HTTP próprios e mensagens de erro acionáveis ("abra o Zotero..."). Dívida conhecida: `write/export.py` hardcoda o endpoint e ignora o env var — corrigir quando aquele módulo for tocado (não justifica release próprio).
