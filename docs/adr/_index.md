---
title: Índice de ADRs
tags: [adr, index]
---

# Decisões registradas (ADRs)

Formato [MADR 4.0](https://adr.github.io/madr/) minimal: Contexto / Decisão / Consequências. ADR aceito é imutável — revisão = ADR novo. Decisão estrutural nova em PR = ADR novo aqui.

<!-- prumo:adr-index:begin -->
- [[adr/adr-0001-adr-log-em-docs-adr]] — ADR log do repo em `docs/adr/`; produto continua gerando `docs/decisions/` · aceito
- [[adr/adr-0002-skills-e-templates-fora-de-src]] — `skills/` e `templates/` fora de `src/`, force-included no wheel · aceito
- [[adr/adr-0003-skill-md-unica-fonte-de-metadata]] — SKILL.md é a única fonte de metadata por skill · aceito
- [[adr/adr-0004-pacote-livre-de-llm]] — O pacote Python é 100% livre de LLM · aceito
- [[adr/adr-0005-layering-core-domains]] — Layering: core ← domains ← fachadas finas · aceito
- [[adr/adr-0006-schemas-forward-only]] — Schemas versionados forward-only · aceito
- [[adr/adr-0007-zotero-stdlib-urllib]] — Zotero/BBT via stdlib urllib, endpoint 127.0.0.1:23119 · aceito
- [[adr/adr-0008-layout-alfa-de-notas]] — Layout α para notas de referência · aceito
- [[adr/adr-0009-blocos-delimitados]] — Blocos delimitados HTML-comment como contrato humano/máquina · aceito
- [[adr/adr-0010-plugin-root-na-raiz]] — Plugin root = raiz do repo; marketplace self-hosting; schemas vivos do validador · aceito
- [[adr/adr-0011-semver-por-visibilidade]] — SemVer por visibilidade ao consumidor; deferrals com trigger · aceito
- [[adr/adr-0012-remocao-agents-ml]] — Remoção dos agents ML pré-pivot · aceito
- [[adr/adr-0013-pdf-via-read-nativo]] — PDFs lidos com a tool Read nativa; sem MCP pdf-reader · aceito
- [[adr/adr-0014-findings-canonico]] — Caminho canônico de findings: `docs/wiki/findings/` com fallback · aceito
<!-- prumo:adr-index:end -->
