# ADR-0005 — Layering: core ← domains ← fachadas finas

- Status: aceito
- Data: 2026-06-11
- Origem: ARCHITECTURE.md ("Por que core/ e domains/ são separados", pré-existente; formalizado nesta data); [[constitution#I · Lógica em um lugar só]]

## Contexto
É preciso poder arrancar um domínio inteiro (spin-off) sem quebrar a fundação, e testar `core/` sem dependências externas instaladas.

## Decisão
`core/` nunca importa de `domains/`; `domains/` importam `core/`; domínios são mutuamente independentes (única exceção: `write` → `protocol`, com ImportError guard em `compose.py`). CLI raiz e `domains/<X>/cli.py` são fachadas finas (`cli_run` + chamada + saída); `domains/<X>/api.py` é re-export puro.

## Consequências
Lógica nova entra em `domains/<X>/<op>.py` com teste espelhado em `tests/unit/<X>/`. Violações de camada são defeito de revisão. Exceções de camada novas exigem justificativa explícita (e idealmente um ADR).
